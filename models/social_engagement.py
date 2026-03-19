"""
Social engagement data model - normalized representation of social platform interactions.

Covers LinkedIn, Twitter/X, Facebook, Instagram, and other social platforms.
Captures all engagement types: messages, comments, likes, shares, connection requests, etc.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from models.base import CommunicationDirection


class SocialEngagement(BaseModel):
    """
    Normalized social engagement model that works with any social platform.

    Supports: LinkedIn, Twitter/X, Facebook, Instagram, etc.
    Covers: messages, InMails, comments, likes, shares, connection requests,
    endorsements, follows, reactions, and posts.
    """

    # Identifiers
    engagement_id: str = Field(..., description="Unique engagement/activity ID")
    platform: str = Field(
        default="linkedin",
        description="Platform: linkedin, twitter, facebook, instagram",
    )

    # Participants
    from_user: str = Field(..., description="Actor name or profile identifier")
    to_user: str = Field(..., description="Target user name or profile identifier")

    # Content
    activity_type: str = Field(
        ...,
        description="Type: message, connection_request, inmail, comment, like, share, post, reaction, endorsement, follow",
    )
    content: Optional[str] = Field(
        None, description="Text content of the engagement (message body, comment text, post text)"
    )
    target_content: Optional[str] = Field(
        None, description="Content being engaged with (post text, article title, etc.)"
    )

    # Metadata
    timestamp: datetime = Field(..., description="When the engagement occurred")
    direction: CommunicationDirection = Field(..., description="Inbound or outbound")
    account_name: Optional[str] = Field(None, description="Matched account name")

    def to_episode_content(self) -> str:
        """
        Format social engagement for Graphiti episode ingestion.

        Returns a structured text representation optimized for
        LLM entity and relationship extraction.
        """
        if self.direction == CommunicationDirection.OUTBOUND:
            direction_context = "Our team member initiated this social engagement"
        else:
            direction_context = "We received this social engagement from external contact"

        content = f"""Social Engagement Record
=========================
From: {self.from_user}
To: {self.to_user}
Activity Type: {self.activity_type}
Platform: {self.platform}
Date: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
Direction: {self.direction.value} ({direction_context})
Account: {self.account_name or 'Unknown Account'}
"""

        if self.target_content:
            content += f"""
Engaged With:
-------------
{self.target_content[:4000]}
"""

        if self.content:
            content += f"""
Content:
--------
{self.content[:8000]}
"""

        if len(content) > 10000:
            content = content[:9500] + "\n\n[Content truncated...]"

        return content
