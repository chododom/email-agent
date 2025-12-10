import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email_agent.models.gmail import (
    EmailHeaders,
    EmailMessage,
    EmailBody,
    EmailAttachment,
)
import base64
import re
from email_agent.utils.logger import logger
from email_agent.config import CFG
from email.mime.text import MIMEText
from googleapiclient.errors import HttpError
from typing import Optional


# Scopes needed for reading and sending
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

#######################
### Setup Functions ###
#######################


def get_gmail_service() -> build:
    """
    Authorizes and builds the Gmail API service client by loading credentials
    from a mounted Secret Manager environment variable.
    """
    try:
        # Load credentials
        info = json.loads(CFG.gmail_service_acc_json.get_secret_value())
        credentials = Credentials.from_authorized_user_info(
            info=info,
            scopes=SCOPES,
        )

        # Build the Gmail service object
        service = build("gmail", "v1", credentials=credentials)
        return service

    except Exception as e:
        logger.error(f"Error building Gmail service or parsing credentials: {e}")
        raise


def renew_watch_instruction(service: build, user_id: str = CFG.user_email):
    """
    Calls the users.watch() instruction to keep the PubSub notification alive.
    """
    try:
        watch_request = {"labelIds": ["INBOX"], "topicName": CFG.pubsub_topic}

        response = service.users().watch(userId=user_id, body=watch_request).execute()

        logger.info(
            f"Gmail watch successfully renewed. New historyId: {response.get('historyId')}"
        )

    except Exception as e:
        logger.error(f"Unexpected error during watch renewal: {e}")
        raise


#####################
### Email Reading ###
#####################


def _parse_headers(headers) -> EmailHeaders:
    """
    Iterate over email headers and assign the required ones to an 'EmailHeaders' instance.
    """
    header_data = {
        "date": None,
        "subject": "",
        "sender": None,
        "message_id": None,
    }

    for header in headers:
        name = header["name"]
        value = header["value"]

        if name == "Date":
            header_data["date"] = value
        elif name == "Subject":
            header_data["subject"] = value
        elif name == "From":
            header_data["sender"] = value
        elif name == "Message-ID":
            header_data["message_id"] = value

        # Stop the loop once all headers are found
        if all(header_data.values()):
            break

    if header_data["message_id"] is None:
        header_data["message_id"] = ""
        logger.warning(
            f"Message from {header_data['sender']} has no message_id, will be skipped."
        )  # Messages from the agent itself

    return EmailHeaders(**header_data)


def _parse_body_parts(message, service: build) -> EmailBody:
    """
    Recursively parses content parts of the email message.
    """
    email_data = {
        "body_text": "",
        "attachments": [],
    }

    def parse_parts(parts):
        for part in parts:
            mime_type = part.get("mimeType")
            body = part.get("body", {})
            data = body.get("data")
            part_headers = part.get("headers", [])

            # Check Content-Disposition (to distinguish inline images vs actual attachments)
            content_disposition = next(
                (
                    h["value"]
                    for h in part_headers
                    if h["name"] == "Content-Disposition"
                ),
                "",
            )

            # Handle text body with text/plain type
            if mime_type == "text/plain" and "attachment" not in content_disposition:
                if data:
                    decoded_text = base64.urlsafe_b64decode(data).decode("utf-8")
                    email_data["body_text"] += decoded_text

            # Handle attachments (filename + attachmentId)
            filename = part.get("filename")
            if filename:
                if "attachmentId" in body:
                    att_id = body["attachmentId"]

                    # Attachments require a separate API call to get the data
                    logger.info(f"Downloading attachment: {filename}...")
                    attachment = (
                        service.users()
                        .messages()
                        .attachments()
                        .get(userId=CFG.user_email, messageId=message["id"], id=att_id)
                        .execute()
                    )

                    file_data_b64 = attachment["data"]
                    raw_file_bytes = base64.urlsafe_b64decode(file_data_b64)

                    email_data["attachments"].append(
                        EmailAttachment.model_validate(
                            {
                                "filename": filename,
                                "mime_type": mime_type,
                                "size": body.get("size"),
                                "data": raw_file_bytes,
                            }
                        )
                    )

            # If the part has subparts, recursively add those
            if "parts" in part:
                parse_parts(part["parts"])

    payload = message["payload"]
    if "parts" in payload:
        parse_parts(payload["parts"])
    else:
        parse_parts([payload])

    return EmailBody(**email_data)


def read_messages(message_ids: set[str], service: build):
    """
    Given a set of message IDs, fetches and processes each email message.
    """
    processed_messages = []

    for msg_id in message_ids:
        try:
            message = (
                service.users()
                .messages()
                .get(userId=CFG.user_email, id=msg_id, format="full")
                .execute()
            )

            header_data = _parse_headers(message["payload"]["headers"])

            sender_info = header_data.sender
            email_match = re.search(r"<(.*?)>", sender_info)
            sender_email = (
                email_match.group(1).strip() if email_match else sender_info.strip()
            )

            # Skip self-sent messages to avoid loops
            if sender_email.lower() == CFG.user_email:
                logger.info(f"Skipping self-sent message {msg_id}.")
                service.users().messages().modify(
                    userId=CFG.user_email,
                    id=msg_id,
                    body={"removeLabelIds": ["UNREAD"]},
                ).execute()
                continue

            email_data = _parse_body_parts(message, service)
            email_message = EmailMessage(
                id=msg_id,
                thread_id=message.get("threadId", ""),
                headers=header_data,
                body=email_data,
            )

            # logger.info("#######################")
            # logger.info("--- METADATA ---")
            # logger.info(f"Subject: {email_message.headers.subject}")
            # logger.info(f"From: {email_message.headers.sender}")
            # logger.info(f"Date: {email_message.headers.date}")
            # logger.info("--- DECODED BODY ---")
            # logger.info(email_message.body.body_text)

            processed_messages.append(email_message)

        except Exception as e:
            logger.error(f"Failed to process message {msg_id}: {e}")
            raise

    return processed_messages


#####################
### Email Sending ###
#####################


def get_or_create_custom_label_id(
    service: build,
    label_name: str,
    background_color: str,
    text_color: str,
    user_id: str = CFG.user_email,
) -> Optional[str]:
    """
    Checks if the custom label exists, creates it if necessary, and returns its API ID.
    """
    try:
        # Check if the label already exists
        response = service.users().labels().list(userId=user_id).execute()
        labels = response.get("labels", [])

        for label in labels:
            if label["name"] == label_name:
                return label["id"]

        # If not found, create the label
        print(f"Custom label '{label_name}' not found. Creating...")
        create_body = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
            "color": {
                "backgroundColor": background_color,
                "textColor": text_color,
            },
        }

        created_label = (
            service.users().labels().create(userId=user_id, body=create_body).execute()
        )

        logger.info(f"Custom label created with ID: {created_label['id']}")
        return created_label["id"]

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise


def send_thread_reply(
    service: build,
    received_message: EmailMessage,
    body_text: str,
    user_id: str = CFG.user_email,
):
    """
    Sends a reply message within the original email thread and marks the thread as read.
    """
    message = MIMEText(body_text)

    # Search for the email address within angle brackets
    email_match = re.search(r"<(.*?)>", received_message.headers.sender)
    if email_match:
        message["to"] = email_match.group(1).strip()
    else:
        # If no angle brackets, assume the entire string is the address
        message["to"] = received_message.headers.sender.strip()

    original_subject = received_message.headers.subject
    thread_id = received_message.thread_id

    # Prepend 'Re:' to the subject if it's not already there
    original_subject = original_subject or ""
    if not original_subject.lower().startswith("re:"):
        message["subject"] = "Re: " + original_subject
    else:
        message["subject"] = original_subject

    message["In-Reply-To"] = received_message.headers.message_id
    message["References"] = (
        received_message.headers.message_id
    )  # Note: For longer threads in multi-turn conversations, this would need to be continuously appended

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    message_body = {"raw": raw_message, "threadId": thread_id}

    try:
        sent_message = (
            service.users().messages().send(userId=user_id, body=message_body).execute()
        )

        # Mark the original thread as read and label it
        answered_label_id = get_or_create_custom_label_id(
            service,
            label_name="Answered by Agent",
            background_color="#16a766",
            text_color="#ffffff",
            user_id=user_id,
        )
        service.users().threads().modify(
            userId=user_id,
            id=thread_id,
            body={"removeLabelIds": ["UNREAD"], "addLabelIds": [answered_label_id]},
        ).execute()

        logger.info(f"Reply sent successfully in thread: {thread_id}")
        return sent_message

    except HttpError as error:
        logger.error(f"An error occurred sending reply: {error}")
        raise


def mark_as_irrelevant(
    service: build,
    received_message: EmailMessage,
    user_id: str = CFG.user_email,
):
    """
    Marks an email thread that was determined as irrelevant with a corresponding label.
    """
    thread_id = received_message.thread_id

    irrelevant_label_id = get_or_create_custom_label_id(
        service,
        label_name="Irrelevant",
        background_color="#cc3a21",
        text_color="#ffffff",
        user_id=user_id,
    )

    service.users().threads().modify(
        userId=user_id,
        id=thread_id,
        body={"removeLabelIds": ["UNREAD"], "addLabelIds": [irrelevant_label_id]},
    ).execute()

    logger.info(f"Message marked as read and labeled irrelevant: {thread_id}")
