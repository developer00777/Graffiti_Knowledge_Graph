"""
Call transcript data model - normalized representation of calls from any provider.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from models.base import CommunicationDirection


class CallTranscript(BaseModel):
    """
    Normalized call transcript model that works with any call/meeting provider.

    Supports: Gong, Zoom, Fireflies, Google Meet, Microsoft Teams, etc.
    """

    # Identifiers
    call_id: str = Field(..., description="Unique call ID from provider")
    provider: str = Field(..., description="Call provider: gong, zoom, fireflies, google_meet, teams")

    # Participants
    caller: str = Field(..., description="Person who initiated the call (name or email)")
    callee: str = Field(..., description="Primary recipient of the call (name or email)")
    other_participants: Optional[List[str]] = Field(
        None, description="Other participants on the call"
    )

    # Timing
    timestamp: datetime = Field(..., description="When the call started")
    duration_minutes: Optional[float] = Field(None, description="Call duration in minutes")

    # Content
    title: Optional[str] = Field(None, description="Call title or meeting name")
    transcript: str = Field(..., description="Full or partial call transcript")
    summary: Optional[str] = Field(None, description="AI-generated or manual summary")

    # Metadata
    direction: CommunicationDirection = Field(..., description="Inbound or outbound")
    account_name: Optional[str] = Field(None, description="Matched account name")

    def to_episode_content(self) -> str:
        """
        Format call transcript for Graphiti episode ingestion.

        Returns a structured text representation optimized for
        LLM entity and relationship extraction.
        """
        participants = [self.caller, self.callee]
        if self.other_participants:
            participants.extend(self.other_participants)

        if self.direction == CommunicationDirection.OUTBOUND:
            direction_context = "Our team member initiated this call"
        else:
            direction_context = "We received this call from external contact"

        duration_str = f"{self.duration_minutes:.0f} minutes" if self.duration_minutes else "Unknown"

        content = f"""Call Transcript Record
=======================
Caller: {self.caller}
Callee: {self.callee}
Other Participants: {', '.join(self.other_participants) if self.other_participants else 'None'}
Date: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
Duration: {duration_str}
Direction: {self.direction.value} ({direction_context})
Account: {self.account_name or 'Unknown Account'}
Provider: {self.provider}
Title: {self.title or '(no title)'}

{f'Summary: {self.summary}' if self.summary else ''}

Transcript:
-----------
{self.transcript[:8000]}
"""
        if len(content) > 10000:
            content = content[:9500] + "\n\n[Content truncated...]"

        return content
