"""
Meeting notes data model - normalized representation of meetings from any provider.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from models.base import CommunicationDirection


class MeetingNotes(BaseModel):
    """
    Normalized meeting model that works with any calendar/meeting provider.

    Supports: Google Calendar, Outlook Calendar, Calendly, etc.
    """

    # Identifiers
    meeting_id: str = Field(..., description="Unique meeting/event ID from provider")
    provider: str = Field(
        ..., description="Meeting provider: google_calendar, outlook_calendar, calendly"
    )

    # Details
    title: str = Field(..., description="Meeting title")
    organizer: str = Field(..., description="Meeting organizer (name or email)")
    attendees: List[str] = Field(
        default_factory=list, description="List of attendee names or emails"
    )

    # Timing
    start_time: datetime = Field(..., description="Meeting start time")
    end_time: Optional[datetime] = Field(None, description="Meeting end time")

    # Content
    notes: str = Field(..., description="Meeting notes, agenda, or summary")

    # Metadata
    direction: CommunicationDirection = Field(
        default=CommunicationDirection.OUTBOUND,
        description="Who organized: outbound = we organized, inbound = they organized"
    )
    account_name: Optional[str] = Field(None, description="Matched account name")

    def to_episode_content(self) -> str:
        """
        Format meeting notes for Graphiti episode ingestion.

        Returns a structured text representation optimized for
        LLM entity and relationship extraction.
        """
        if self.direction == CommunicationDirection.OUTBOUND:
            direction_context = "Our team organized this meeting"
        else:
            direction_context = "External contact organized this meeting"

        duration_str = ""
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds() / 60
            duration_str = f"\nDuration: {duration:.0f} minutes"

        attendees_str = ", ".join(self.attendees[:10])
        if len(self.attendees) > 10:
            attendees_str += f" and {len(self.attendees) - 10} others"

        content = f"""Meeting Record
===============
Title: {self.title}
Organizer: {self.organizer}
Attendees: {attendees_str}
Date: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}{duration_str}
Direction: {self.direction.value} ({direction_context})
Account: {self.account_name or 'Unknown Account'}
Provider: {self.provider}

Notes:
------
{self.notes[:8000]}
"""
        if len(content) > 10000:
            content = content[:9500] + "\n\n[Content truncated...]"

        return content
