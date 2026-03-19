"""
Text message data model - normalized representation of SMS/text messages from any provider.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from models.base import CommunicationDirection


class TextMessage(BaseModel):
    """
    Normalized text message model that works with any SMS/messaging provider.

    Supports: Twilio, Vonage, MessageBird, etc.
    """

    # Identifiers
    message_id: str = Field(..., description="Unique message ID from provider")
    provider: str = Field(..., description="SMS provider: twilio, vonage, messagebird")

    # Participants
    from_identifier: str = Field(
        ..., description="Sender phone number, name, or identifier"
    )
    to_identifier: str = Field(
        ..., description="Recipient phone number, name, or identifier"
    )

    # Content
    body: str = Field(..., description="Message text content")

    # Metadata
    timestamp: datetime = Field(..., description="When the message was sent")
    direction: CommunicationDirection = Field(..., description="Inbound or outbound")
    channel: str = Field(default="sms", description="Channel: sms, whatsapp, imessage")
    account_name: Optional[str] = Field(None, description="Matched account name")
    conversation_id: Optional[str] = Field(None, description="Conversation thread ID")
    is_reply: bool = Field(default=False, description="Is this a reply to a previous message?")

    def to_episode_content(self) -> str:
        """
        Format text message for Graphiti episode ingestion.

        Returns a structured text representation optimized for
        LLM entity and relationship extraction.
        """
        if self.direction == CommunicationDirection.OUTBOUND:
            direction_context = "Our team member sent this message"
        else:
            direction_context = "We received this message from external contact"

        content = f"""Text Message Record
====================
From: {self.from_identifier}
To: {self.to_identifier}
Date: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
Direction: {self.direction.value} ({direction_context})
Account: {self.account_name or 'Unknown Account'}
Channel: {self.channel}
Is Reply: {'Yes' if self.is_reply else 'No'}

Message:
--------
{self.body}
"""
        if len(content) > 10000:
            content = content[:9500] + "\n\n[Content truncated...]"

        return content
