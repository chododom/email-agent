from pydantic import BaseModel
from typing import List, Optional


class EmailAttachment(BaseModel):
    """Represents an email attachment and its headers and content."""

    filename: str
    mime_type: str
    size: int
    data: bytes


class EmailBody(BaseModel):
    """Represents the email contents."""

    body_text: str
    attachments: Optional[List[EmailAttachment]] = []


class EmailHeaders(BaseModel):
    """Represents the email headers."""

    message_id: str
    date: str
    subject: str
    sender: str


class EmailMessage(BaseModel):
    """Represents a complete email message along with all its metadata and contents."""

    id: str
    thread_id: str
    headers: EmailHeaders
    body: EmailBody
