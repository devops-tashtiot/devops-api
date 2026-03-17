from pydantic import BaseModel, Field
from enum import Enum

class STATUSES(Enum):
    SENT   = "sent"
    FAILED = "failed"

class ChatMessage(BaseModel):
    
    message: str = Field(
        ...,
        description="message to send",
    )

    recipients: list = Field(
        ...,
        description="message receiver",
    )


class MessageStatus(BaseModel):

    status: STATUSES = Field(
        ...,
        description="message status",
    )