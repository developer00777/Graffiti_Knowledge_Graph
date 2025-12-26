"""
Email data model - normalized representation of emails from any provider.
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class EmailDirection(str, Enum):
    """Direction of email communication"""
    INBOUND = "inbound"    # They sent to us
    OUTBOUND = "outbound"  # We sent to them


class Email(BaseModel):
    """
    Normalized email model that works with any email provider.

    This model represents a single email message with all relevant
    metadata for knowledge graph extraction.
    """

    # Identifiers
    message_id: str = Field(..., description="Unique message ID from provider")
    thread_id: Optional[str] = Field(None, description="Conversation thread ID")

    # Sender
    from_email: str = Field(..., description="Sender email address")
    from_name: Optional[str] = Field(None, description="Sender display name")

    # Recipients
    to_emails: List[str] = Field(default_factory=list, description="To recipients")
    to_names: Optional[List[str]] = Field(None, description="To recipient names")
    cc_emails: Optional[List[str]] = Field(None, description="CC recipients")
    bcc_emails: Optional[List[str]] = Field(None, description="BCC recipients")

    # Content
    subject: str = Field(default="(no subject)", description="Email subject")
    body_text: str = Field(default="", description="Plain text body")
    body_html: Optional[str] = Field(None, description="HTML body (if available)")

    # Metadata
    timestamp: datetime = Field(..., description="Send/receive timestamp")
    direction: EmailDirection = Field(..., description="Inbound or outbound")
    channel: str = Field(default="email", description="Communication channel")

    # Account mapping (enriched after fetching)
    account_name: Optional[str] = Field(None, description="Matched account name")
    account_domain: Optional[str] = Field(None, description="Primary account domain")

    # Additional metadata
    labels: Optional[List[str]] = Field(None, description="Email labels/folders")
    is_reply: bool = Field(default=False, description="Is this a reply?")
    has_attachments: bool = Field(default=False, description="Has attachments?")

    # Provider-specific
    provider: str = Field(default="unknown", description="Email provider: gmail, outlook")
    raw_data: Optional[dict] = Field(None, description="Raw provider data (for debugging)")

    def to_episode_content(self) -> str:
        """
        Format email for Graphiti episode ingestion.

        Returns a structured text representation optimized for
        LLM entity and relationship extraction.
        """
        # Format recipients
        recipients = ", ".join(self.to_emails[:5])
        if len(self.to_emails) > 5:
            recipients += f" and {len(self.to_emails) - 5} others"

        # CC line if present
        cc_line = ""
        if self.cc_emails:
            cc_recipients = ", ".join(self.cc_emails[:3])
            if len(self.cc_emails) > 3:
                cc_recipients += f" and {len(self.cc_emails) - 3} others"
            cc_line = f"\nCC: {cc_recipients}"

        # Direction context
        if self.direction == EmailDirection.OUTBOUND:
            direction_context = "Our team member sent this email"
        else:
            direction_context = "We received this email from external contact"

        # Build the episode content
        content = f"""Email Communication Record
===========================
From: {self.from_name or self.from_email} <{self.from_email}>
To: {recipients}{cc_line}
Subject: {self.subject}
Date: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
Direction: {self.direction.value} ({direction_context})
Account: {self.account_name or 'Unknown Account'}
Channel: {self.channel}
Is Reply: {'Yes' if self.is_reply else 'No'}

Email Body:
-----------
{self.body_text[:8000]}
"""
        # Truncate if too long (Graphiti has limits)
        if len(content) > 10000:
            content = content[:9500] + "\n\n[Content truncated...]"

        return content

    def get_external_participants(self, team_domains: List[str]) -> List[str]:
        """Get list of external (non-team) email addresses"""
        all_participants = [self.from_email] + self.to_emails + (self.cc_emails or [])
        return [
            email for email in all_participants
            if not any(domain in email.lower() for domain in team_domains)
        ]

    def get_team_participants(self, team_domains: List[str]) -> List[str]:
        """Get list of team email addresses"""
        all_participants = [self.from_email] + self.to_emails + (self.cc_emails or [])
        return [
            email for email in all_participants
            if any(domain in email.lower() for domain in team_domains)
        ]

    @property
    def from_domain(self) -> str:
        """Extract domain from sender email"""
        if '@' in self.from_email:
            return self.from_email.split('@')[1].lower()
        return ""

    @property
    def primary_recipient_domain(self) -> Optional[str]:
        """Extract domain from first recipient"""
        if self.to_emails and '@' in self.to_emails[0]:
            return self.to_emails[0].split('@')[1].lower()
        return None
