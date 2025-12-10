from typing import List, TypedDict
from pydantic import BaseModel, Field
from email_agent.models.gmail import EmailMessage
from langchain_core.messages import BaseMessage


class AgentState(TypedDict, total=False):
    """
    Agent state dictionary.

    - email: the incoming `EmailMessage` to reply to
    - attachments_text: extracted text from attachments (PDF/image/audio)
    - is_relevant: whether or not the email message is relevant or to be filtered out
    - tool_results_context: concatenated strings returned from RAG search
    - tool_calls: stores requested tool calls
    - reply: the generated reply text
    - history: history of messages
    """

    email: EmailMessage
    attachments_text: List[str]
    is_relevant: bool
    tool_results_context: str
    tool_calls: List[dict]
    reply: str
    history: List[BaseMessage]


class RelevanceAssessment(BaseModel):
    """Schema for classifying the relevance of an email."""

    is_relevant: bool = Field(
        description="True if the email appears to be a serious, business-relevant, or product-related inquiry. False if it is spam, inappropriate, promotional, or completely irrelevant."
    )
    reason: str = Field(description="A brief explanation for the relevance decision.")
