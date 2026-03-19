"""
API request and response models for CHAMP Graph.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- Error responses ---


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail


# --- Health ---


class HealthResponse(BaseModel):
    status: str  # healthy | degraded | unhealthy
    service: str
    version: str
    neo4j_connected: bool
    uptime_seconds: float


# --- Ingest ---


class IngestMode(str, Enum):
    RAW = "raw"
    EMAIL = "email"
    CALL = "call"
    TEXT_MSG = "text_message"
    SOCIAL = "social"
    MEETING = "meeting"


class IngestRequest(BaseModel):
    """
    Dual-mode ingest endpoint.

    Mode 1 (raw): Provide content + metadata directly.
    Mode 2 (structured): Provide a typed model body that gets
    converted to episode content via to_episode_content().
    """

    account_name: str = Field(..., description="Target account name (used as group_id)")
    mode: IngestMode = Field(default=IngestMode.RAW, description="Ingestion mode")

    # Mode 1: Raw content
    content: Optional[str] = Field(None, description="Raw text content for episode (mode=raw)")
    name: Optional[str] = Field(None, description="Episode name (mode=raw)")
    source_description: Optional[str] = Field(None, description="Source description")
    reference_time: Optional[datetime] = Field(None, description="When this interaction occurred")

    # Mode 2: Structured model body
    data: Optional[Dict[str, Any]] = Field(
        None, description="Structured model body matching the mode's schema"
    )


class IngestResponse(BaseModel):
    success: bool = True
    message: str
    account_name: str
    episodes_ingested: int = 1


class BulkIngestItem(BaseModel):
    """Single item in a bulk ingest request."""

    mode: IngestMode = Field(default=IngestMode.RAW)
    content: Optional[str] = None
    name: Optional[str] = None
    source_description: Optional[str] = None
    reference_time: Optional[datetime] = None
    data: Optional[Dict[str, Any]] = None


class BulkIngestRequest(BaseModel):
    account_name: str = Field(..., description="Target account name")
    items: List[BulkIngestItem] = Field(..., min_length=1, max_length=500)


class BulkIngestResponse(BaseModel):
    success: bool = True
    message: str
    account_name: str
    episodes_ingested: int
    errors: List[str] = Field(default_factory=list)


# --- Sync ---


class SyncTriggerRequest(BaseModel):
    source_type: str = Field(default="email", description="Source type to sync")
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    full_sync: bool = False


class SyncTriggerResponse(BaseModel):
    success: bool = True
    message: str
    account_name: str
    items_processed: int = 0


class SyncStatusResponse(BaseModel):
    success: bool = True
    accounts: Dict[str, Dict[str, Optional[str]]]


# --- Query ---


class QueryRequest(BaseModel):
    account: str
    query: str
    num_results: int = 20


class QueryResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    message: Optional[str] = None


# --- Timeline ---


class TimelineEntry(BaseModel):
    timestamp: Optional[str] = None
    channel: str
    name: str
    summary: Optional[str] = None
    direction: Optional[str] = None


class TimelineResponse(BaseModel):
    success: bool = True
    account_name: str
    timeline: List[TimelineEntry]
    total: int


# --- Relationships ---


class RelationshipEntry(BaseModel):
    source: str
    target: str
    relationship_type: str
    fact: Optional[str] = None
    valid_at: Optional[str] = None


class RelationshipsResponse(BaseModel):
    success: bool = True
    account_name: str
    relationships: List[RelationshipEntry]
    total: int


# --- Webhook (simplified agent-friendly payloads) ---


class EmailHookRequest(BaseModel):
    """Simplified email payload for agent hooks (CHAMP Mail, etc.)."""

    account_name: str = Field(..., description="Target account name")
    from_address: str = Field(..., description="Sender email address")
    to_address: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Email body text")
    direction: str = Field(default="outbound", description="'outbound' or 'inbound'")


class EmailHookBatchRequest(BaseModel):
    """Batch email hook payload."""

    account_name: str = Field(..., description="Target account name")
    emails: List[EmailHookRequest] = Field(..., min_length=1, max_length=100)


class CallHookRequest(BaseModel):
    """Simplified call payload for agent hooks."""

    account_name: str = Field(..., description="Target account name")
    contact_name: str = Field(..., description="Who the call was with")
    summary: str = Field(..., description="Brief summary of the call")
    duration_minutes: int = Field(default=0, description="Call duration in minutes")
    direction: str = Field(default="outbound", description="'outbound' or 'inbound'")
    transcript: str = Field(default="", description="Full transcript if available")
