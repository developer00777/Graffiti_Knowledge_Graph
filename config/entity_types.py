"""
Custom entity types for CHAMP Graph knowledge graph extraction.

These Pydantic models guide the LLM to extract specific entity types
from multi-modal communication content (emails, calls, SMS, LinkedIn, meetings),
improving extraction accuracy for sales/marketing use cases.
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class Contact(BaseModel):
    """A person at a target account (prospect, customer, etc.)"""
    name: str = Field(..., description="Full name of the contact")
    email: Optional[str] = Field(None, description="Email address")
    title: Optional[str] = Field(None, description="Job title or role")
    department: Optional[str] = Field(None, description="Department they work in")


class Account(BaseModel):
    """A target company/account (MQA - Marketing Qualified Account)"""
    name: str = Field(..., description="Company or organization name")
    domain: Optional[str] = Field(None, description="Primary email domain")
    industry: Optional[str] = Field(None, description="Industry vertical")


class TeamMember(BaseModel):
    """A member of your internal sales/marketing team"""
    name: str = Field(..., description="Full name of team member")
    email: Optional[str] = Field(None, description="Email address")
    role: Optional[str] = Field(None, description="Role: SDR, AE, CSM, Marketing, etc.")


class PersonalDetail(BaseModel):
    """Personal information mentioned about a contact.

    This captures personal tidbits like family info, hobbies, interests,
    preferences, etc. that can help build rapport.
    """
    category: str = Field(
        ...,
        description="Category of detail: family, hobby, interest, preference, travel, sports, etc."
    )
    detail: str = Field(..., description="The specific personal detail mentioned")


class Topic(BaseModel):
    """A discussion topic or business theme"""
    name: str = Field(..., description="Name of the topic or theme")
    category: Optional[str] = Field(
        None,
        description="Category: pricing, product, support, partnership, contract, demo, etc."
    )


class Communication(BaseModel):
    """A communication event or interaction"""
    channel: str = Field(
        ...,
        description="Channel: email, phone, linkedin, meeting, conference, slack"
    )
    direction: str = Field(
        ...,
        description="Direction: outbound (we initiated) or inbound (they initiated)"
    )
    sentiment: Optional[str] = Field(
        None,
        description="Sentiment: positive, neutral, negative"
    )


class Opportunity(BaseModel):
    """A sales opportunity or deal being pursued with an account"""
    name: str = Field(..., description="Opportunity or deal name")
    stage: Optional[str] = Field(
        None,
        description="Stage: prospect, discovery, proposal, negotiation, closed-won, closed-lost"
    )
    value: Optional[str] = Field(None, description="Estimated deal value")


class Branch(BaseModel):
    """A branch, division, or business unit of an account"""
    name: str = Field(..., description="Branch, division, or business unit name")
    location: Optional[str] = Field(None, description="Geographic location")
    parent_account: Optional[str] = Field(None, description="Parent company name")


# Entity types dictionary for Graphiti
ENTITY_TYPES = {
    'Contact': Contact,
    'Account': Account,
    'TeamMember': TeamMember,
    'PersonalDetail': PersonalDetail,
    'Topic': Topic,
    'Communication': Communication,
    'Opportunity': Opportunity,
    'Branch': Branch,
}
