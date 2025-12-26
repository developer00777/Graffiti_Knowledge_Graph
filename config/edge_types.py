"""
Custom edge (relationship) types for email knowledge graph.

These define the relationships between entities that can be extracted.
"""
from typing import Optional
from pydantic import BaseModel, Field


class SentEmailTo(BaseModel):
    """Relationship: Someone sent an email to someone else"""
    subject: Optional[str] = Field(None, description="Email subject line")


class WorksAt(BaseModel):
    """Relationship: A contact works at an account/company"""
    title: Optional[str] = Field(None, description="Job title at the company")
    department: Optional[str] = Field(None, description="Department")


class ReportsTo(BaseModel):
    """Relationship: A contact reports to another contact (org structure)"""
    relationship: Optional[str] = Field(None, description="Nature of reporting relationship")


class HasPersonalDetail(BaseModel):
    """Relationship: A contact has a personal detail associated with them"""
    mentioned_date: Optional[str] = Field(None, description="When this was mentioned")


class DiscussedTopic(BaseModel):
    """Relationship: A communication discussed a specific topic"""
    context: Optional[str] = Field(None, description="Context of the discussion")


class RespondedVia(BaseModel):
    """Relationship: A contact responded via a specific channel"""
    response_time_hours: Optional[float] = Field(None, description="Hours until response")


class InterestedIn(BaseModel):
    """Relationship: A contact expressed interest in something"""
    level: Optional[str] = Field(None, description="Interest level: high, medium, low")


class MentionedBy(BaseModel):
    """Relationship: A topic or person was mentioned by someone"""
    sentiment: Optional[str] = Field(None, description="Sentiment when mentioned")


# Edge types dictionary for Graphiti
EDGE_TYPES = {
    'SENT_EMAIL_TO': SentEmailTo,
    'WORKS_AT': WorksAt,
    'REPORTS_TO': ReportsTo,
    'HAS_PERSONAL_DETAIL': HasPersonalDetail,
    'DISCUSSED_TOPIC': DiscussedTopic,
    'RESPONDED_VIA': RespondedVia,
    'INTERESTED_IN': InterestedIn,
    'MENTIONED_BY': MentionedBy,
}

# Edge type mapping: defines which edge types can connect which node types
# Format: (source_type, target_type): [list of allowed edge types]
EDGE_TYPE_MAP = {
    ('TeamMember', 'Contact'): ['SENT_EMAIL_TO'],
    ('Contact', 'TeamMember'): ['SENT_EMAIL_TO'],
    ('Contact', 'Account'): ['WORKS_AT'],
    ('Contact', 'Contact'): ['REPORTS_TO'],
    ('Contact', 'PersonalDetail'): ['HAS_PERSONAL_DETAIL'],
    ('Contact', 'Topic'): ['DISCUSSED_TOPIC', 'INTERESTED_IN'],
    ('TeamMember', 'Topic'): ['DISCUSSED_TOPIC'],
    ('Communication', 'Topic'): ['DISCUSSED_TOPIC'],
    ('Contact', 'Communication'): ['RESPONDED_VIA'],
}
