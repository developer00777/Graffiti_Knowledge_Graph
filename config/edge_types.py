"""
Custom edge (relationship) types for CHAMP Graph knowledge graph.

These define the relationships between entities that can be extracted
from multi-modal communication data (emails, calls, SMS, LinkedIn, meetings).
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


# --- Multi-modal communication edge types ---


class Called(BaseModel):
    """Relationship: Someone called or had a video call with someone else"""
    duration_minutes: Optional[float] = Field(None, description="Call duration in minutes")
    summary: Optional[str] = Field(None, description="Brief call summary")


class Texted(BaseModel):
    """Relationship: Someone sent a text/SMS to someone else"""
    message_preview: Optional[str] = Field(None, description="First 100 chars of message")


class MetWith(BaseModel):
    """Relationship: Someone met with someone else (in-person or virtual)"""
    meeting_type: Optional[str] = Field(None, description="Meeting type: in-person, virtual, hybrid")
    attendees_count: Optional[int] = Field(None, description="Total number of attendees")


class ConnectedOn(BaseModel):
    """Relationship: Someone connected with someone on a platform (e.g., LinkedIn)"""
    platform: Optional[str] = Field(None, description="Platform: linkedin, twitter, etc.")


# --- Organizational and opportunity edge types ---


class BelongsToBranch(BaseModel):
    """Relationship: A contact or branch belongs to a parent entity"""
    primary: Optional[bool] = Field(None, description="Is this the primary location/branch?")


class HasOpportunity(BaseModel):
    """Relationship: An account has a sales opportunity"""
    created_date: Optional[str] = Field(None, description="When the opportunity was identified")


class InvolvedIn(BaseModel):
    """Relationship: A contact or team member is involved in an opportunity"""
    role: Optional[str] = Field(
        None,
        description="Role: champion, blocker, influencer, decision-maker, technical-evaluator"
    )


class CoversAccount(BaseModel):
    """Relationship: A team member is assigned to cover an account"""
    territory: Optional[str] = Field(None, description="Territory or segment")
    primary: Optional[bool] = Field(None, description="Is this the primary account owner?")


# Edge types dictionary for Graphiti
EDGE_TYPES = {
    # Email
    'SENT_EMAIL_TO': SentEmailTo,
    # Organizational
    'WORKS_AT': WorksAt,
    'REPORTS_TO': ReportsTo,
    'BELONGS_TO_BRANCH': BelongsToBranch,
    'COVERS_ACCOUNT': CoversAccount,
    # Personal
    'HAS_PERSONAL_DETAIL': HasPersonalDetail,
    # Communication
    'DISCUSSED_TOPIC': DiscussedTopic,
    'RESPONDED_VIA': RespondedVia,
    'INTERESTED_IN': InterestedIn,
    'MENTIONED_BY': MentionedBy,
    # Multi-modal interactions
    'CALLED': Called,
    'TEXTED': Texted,
    'MET_WITH': MetWith,
    'CONNECTED_ON': ConnectedOn,
    # Opportunity
    'HAS_OPPORTUNITY': HasOpportunity,
    'INVOLVED_IN': InvolvedIn,
}

# Edge type mapping: defines which edge types can connect which node types
# Format: (source_type, target_type): [list of allowed edge types]
EDGE_TYPE_MAP = {
    # TeamMember <-> Contact interactions (all channels)
    ('TeamMember', 'Contact'): ['SENT_EMAIL_TO', 'CALLED', 'TEXTED', 'MET_WITH', 'CONNECTED_ON'],
    ('Contact', 'TeamMember'): ['SENT_EMAIL_TO', 'CALLED', 'TEXTED', 'MET_WITH', 'CONNECTED_ON'],
    # Organizational structure
    ('Contact', 'Account'): ['WORKS_AT'],
    ('Contact', 'Contact'): ['REPORTS_TO'],
    ('Contact', 'Branch'): ['BELONGS_TO_BRANCH'],
    ('Branch', 'Account'): ['BELONGS_TO_BRANCH'],
    ('TeamMember', 'Account'): ['COVERS_ACCOUNT'],
    # Personal details
    ('Contact', 'PersonalDetail'): ['HAS_PERSONAL_DETAIL'],
    # Topics and interests
    ('Contact', 'Topic'): ['DISCUSSED_TOPIC', 'INTERESTED_IN'],
    ('TeamMember', 'Topic'): ['DISCUSSED_TOPIC'],
    ('Communication', 'Topic'): ['DISCUSSED_TOPIC'],
    # Communication events
    ('Contact', 'Communication'): ['RESPONDED_VIA'],
    # Opportunities
    ('Account', 'Opportunity'): ['HAS_OPPORTUNITY'],
    ('Contact', 'Opportunity'): ['INVOLVED_IN'],
    ('TeamMember', 'Opportunity'): ['INVOLVED_IN'],
}
