from fastapi import APIRouter, Response
from email_agent.models.request import EmailPush
from email_agent.utils.logger import logger
from email_agent.services.gmail import (
    get_gmail_service,
    read_messages,
    send_thread_reply,
    mark_as_irrelevant,
)
from email_agent.services.firestore import firestore_service
from email_agent.config import CFG
from email_agent.agent.graph import agent_executor


router = APIRouter()


@router.post("/gmail-webhook")
async def answer_email(request: EmailPush):
    """
    Handles the agentic processing of an email message delivered by the Gmail API trigger.
    """
    logger.info(request)
    new_history_id = request.message.data["historyId"]

    try:
        last_processed_history_id = await firestore_service.get_last_history_id()
        if last_processed_history_id is None:
            logger.warning(
                "No last history ID found, the Gmail watch has not yet been set up."
            )
            return Response(status_code=200)

        service = get_gmail_service()
        history_response = (
            service.users()
            .history()
            .list(
                userId=CFG.user_email,
                startHistoryId=last_processed_history_id,
                labelId="UNREAD",
            )
            .execute()
        )

        history_records = history_response.get("history")

        # No new emails to process, save current inbox status ID and finish
        if not history_records:
            logger.info("No new UNREAD history records found since last check.")
            final_history_id = history_response.get("historyId", new_history_id)
            await firestore_service.set_last_history_id(final_history_id)
            return Response(status_code=200)

        # Look for newly added email messages
        new_message_ids = set()
        for record in history_records:
            if "messagesAdded" in record:
                for msg_data in record["messagesAdded"]:
                    new_message_ids.add(msg_data["message"]["id"])

        logger.info(f"Found {len(new_message_ids)} new messages to process.")

        processed_messages = read_messages(new_message_ids, service)
        for msg in processed_messages:
            # Perform message deduplication (PubSub or Gmail push trigger seem to deliver multiple times)
            is_first_time_processing = (
                await firestore_service.check_and_set_processed_message(msg.id)
            )
            if not is_first_time_processing:
                logger.warning(
                    f"Skipping duplicate processing for message ID: {msg.id}"
                )
                continue

            # If new message, trigger agentic workflow
            final_state = await agent_executor.ainvoke({"email": msg})

            # Do not respond to irrelevant emails, mark as read and attach dedicated label
            if not final_state["is_relevant"]:
                logger.warning(
                    "The agent marked the email message as not relevant, labeling it as such and not sending an automted reply..."
                )
                mark_as_irrelevant(service=service, received_message=msg)
                await firestore_service.set_last_history_id(new_history_id)
                return Response(status_code=200)

            # For relevant emails, send the reply to the original sender
            reply_text = final_state["reply"]
            send_thread_reply(
                service=service,
                received_message=msg,
                body_text=reply_text,
            )

        final_history_id = history_response["historyId"]
        await firestore_service.set_last_history_id(final_history_id)

    except Exception as e:
        logger.error(f"Error processing Gmail webhook: {e}")
        await firestore_service.set_last_history_id(
            new_history_id
        )  # Fallback saves the current inbox state to avoid continuously processing a message that causes an error

    return Response(status_code=200)
