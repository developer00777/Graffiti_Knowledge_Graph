"""
CHAMP Graph API Server

Centralized High-context Agent Memory Platform.
Provides REST endpoints for ingesting multi-modal data and querying
the knowledge graph.
"""
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.auth import verify_api_key
from api.ingest_helpers import resolve_episode
from api.models import (
    BulkIngestRequest,
    BulkIngestResponse,
    CallHookRequest,
    EmailHookBatchRequest,
    EmailHookRequest,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    RelationshipsResponse,
    SyncStatusResponse,
    SyncTriggerRequest,
    SyncTriggerResponse,
    TimelineResponse,
)
from config.settings import get_settings
from services.graphiti_service import GraphitiService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global service instances
graphiti_service: Optional[GraphitiService] = None
sync_service = None  # Set in Phase 6
_start_time: float = 0.0


def _require_service() -> GraphitiService:
    """Get the graphiti service or raise 503."""
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return graphiti_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global graphiti_service, sync_service, _start_time
    _start_time = time.time()
    settings = get_settings()

    graphiti_service = GraphitiService(
        neo4j_uri=settings.neo4j_uri,
        neo4j_user=settings.neo4j_user,
        neo4j_password=settings.neo4j_password,
        openai_api_key=settings.openai_api_key,
        openai_base_url=settings.openai_base_url,
        model_name=settings.model_name,
    )

    await graphiti_service.connect()
    logger.info("CHAMP Graph service connected")

    # Phase 6: SyncService initialization will go here
    # sync_service = SyncService(graphiti_service=graphiti_service)

    yield

    await graphiti_service.disconnect()
    logger.info("CHAMP Graph service disconnected")


app = FastAPI(
    title="CHAMP Graph API",
    description="Centralized High-context Agent Memory Platform — Knowledge graph service for multi-modal communication intelligence",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount MCP server for agent tool discovery
from mcp_server import mcp as mcp_server

app.mount("/mcp", mcp_server.http_app())
logger.info("MCP server available at /mcp")


# ============================================================
# Health (no auth required)
# ============================================================


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check with Neo4j connectivity test."""
    neo4j_ok = False
    if graphiti_service and graphiti_service.client:
        try:
            neo4j_ok = True
        except Exception:
            neo4j_ok = False

    status = "healthy" if neo4j_ok else "degraded"
    if not graphiti_service:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        service="champ-graph",
        version="2.0.0",
        neo4j_connected=neo4j_ok,
        uptime_seconds=round(time.time() - _start_time, 1) if _start_time else 0,
    )


# ============================================================
# Ingest endpoints (the core integration surface)
# ============================================================


@app.post(
    "/api/ingest",
    response_model=IngestResponse,
    dependencies=[Depends(verify_api_key)],
)
async def ingest_episode(request: IngestRequest):
    """
    Ingest a single episode into the knowledge graph.

    Dual-mode:
    - mode=raw: provide content + metadata directly
    - mode=email|call|text_message|social|meeting: provide structured data dict
    """
    service = _require_service()

    try:
        content, name, source_desc, ref_time = resolve_episode(request, request.account_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    await service.ingest_episode(
        content=content,
        name=name,
        account_name=request.account_name,
        source_description=source_desc,
        reference_time=ref_time,
    )

    return IngestResponse(
        message="Episode ingested",
        account_name=request.account_name,
    )


@app.post(
    "/api/ingest/batch",
    response_model=BulkIngestResponse,
    dependencies=[Depends(verify_api_key)],
)
async def ingest_batch(request: BulkIngestRequest):
    """Bulk ingest multiple episodes (up to 500)."""
    service = _require_service()

    episodes = []
    errors = []

    for i, item in enumerate(request.items):
        try:
            content, name, source_desc, ref_time = resolve_episode(item, request.account_name)
            episodes.append(
                {
                    "name": name,
                    "content": content,
                    "reference_time": ref_time,
                    "source_description": source_desc,
                }
            )
        except Exception as e:
            errors.append(f"Item {i}: {str(e)}")

    if episodes:
        await service.ingest_episodes_bulk(episodes, request.account_name)

    return BulkIngestResponse(
        message=f"Ingested {len(episodes)} episodes",
        account_name=request.account_name,
        episodes_ingested=len(episodes),
        errors=errors,
    )


# ============================================================
# Sync endpoints
# ============================================================


@app.post(
    "/api/sync/{account_name}",
    response_model=SyncTriggerResponse,
    dependencies=[Depends(verify_api_key)],
)
async def trigger_sync(
    account_name: str,
    request: SyncTriggerRequest = SyncTriggerRequest(),
):
    """Trigger adapter-based sync for an account."""
    if not sync_service:
        raise HTTPException(
            status_code=501,
            detail="Sync service not configured. Use POST /api/ingest to push data directly.",
        )

    task = await sync_service.sync_account(
        account_name=account_name,
        source_type=request.source_type,
        since=request.since,
        until=request.until,
        full_sync=request.full_sync,
    )

    return SyncTriggerResponse(
        message=f"Sync {task.status}: {task.items_processed} items processed",
        account_name=account_name,
        items_processed=task.items_processed,
    )


@app.get(
    "/api/sync/status",
    response_model=SyncStatusResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_sync_status():
    """Get sync state for all accounts."""
    if not sync_service:
        return SyncStatusResponse(accounts={})

    return SyncStatusResponse(accounts=sync_service.get_sync_status())


# ============================================================
# Query endpoints (existing + new)
# ============================================================


@app.post(
    "/api/query",
    response_model=QueryResponse,
    dependencies=[Depends(verify_api_key)],
)
async def query_account(request: QueryRequest):
    """Query the knowledge graph for an account."""
    service = _require_service()

    try:
        results = await service.search_account(
            account_name=request.account,
            query=request.query,
            num_results=request.num_results,
        )
        return QueryResponse(success=True, data=results)
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/accounts/{account_name}/contacts", dependencies=[Depends(verify_api_key)])
async def get_account_contacts(account_name: str):
    """Get all contacts for an account."""
    service = _require_service()
    results = await service.search_account(
        account_name=account_name,
        query="Who are the contacts and people at this account?",
    )
    return {"success": True, "contacts": results.get("nodes", [])}


@app.get("/api/accounts/{account_name}/topics", dependencies=[Depends(verify_api_key)])
async def get_account_topics(account_name: str):
    """Get all topics discussed with an account."""
    service = _require_service()
    results = await service.search_account(
        account_name=account_name,
        query="What topics, subjects, and themes were discussed?",
    )
    return {"success": True, "topics": results.get("edges", [])}


@app.get("/api/accounts/{account_name}/communications", dependencies=[Depends(verify_api_key)])
async def get_account_communications(account_name: str, limit: int = 10):
    """Get recent communications with an account."""
    service = _require_service()
    results = await service.query_recent_communications(
        account_name=account_name,
        limit=limit,
    )
    return {"success": True, "communications": results}


@app.get("/api/accounts/{account_name}/personal-details", dependencies=[Depends(verify_api_key)])
async def get_personal_details(account_name: str):
    """Get personal details about contacts at an account."""
    service = _require_service()
    results = await service.query_personal_details(account_name)
    return {"success": True, "personal_details": results}


@app.get("/api/accounts/{account_name}/team-contacts", dependencies=[Depends(verify_api_key)])
async def get_team_contacts(account_name: str):
    """Get which team members contacted this account."""
    service = _require_service()
    results = await service.query_who_reached_out(account_name)
    return {"success": True, "team_contacts": results}


@app.get("/api/accounts/{account_name}/graph", dependencies=[Depends(verify_api_key)])
async def get_account_graph(account_name: str):
    """Get full graph data for visualization."""
    service = _require_service()
    results = await service.get_account_graph(account_name)
    return {"success": True, "graph": results}


# ============================================================
# Timeline & Relationships
# ============================================================


@app.get(
    "/api/accounts/{account_name}/timeline",
    response_model=TimelineResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_account_timeline(account_name: str, limit: int = 50):
    """Cross-channel communication timeline for an account."""
    service = _require_service()
    timeline = await service.query_timeline(account_name=account_name, limit=limit)
    return TimelineResponse(
        account_name=account_name,
        timeline=timeline,
        total=len(timeline),
    )


@app.get(
    "/api/accounts/{account_name}/relationships",
    response_model=RelationshipsResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_account_relationships(account_name: str):
    """Contact relationship map for an account."""
    service = _require_service()
    relationships = await service.query_relationship_map(account_name)
    return RelationshipsResponse(
        account_name=account_name,
        relationships=relationships,
        total=len(relationships),
    )


# ============================================================
# Intelligence endpoints (Phase 7)
# ============================================================


@app.get(
    "/api/accounts/{account_name}/intelligence/salesperson-overlap",
    dependencies=[Depends(verify_api_key)],
)
async def get_salesperson_overlap(account_name: str):
    """Contacts engaged by multiple team members."""
    service = _require_service()
    results = await service.query_cross_salesperson_overlap(account_name)
    return {"success": True, "account_name": account_name, "overlaps": results}


@app.get(
    "/api/accounts/{account_name}/intelligence/stakeholder-map",
    dependencies=[Depends(verify_api_key)],
)
async def get_stakeholder_map(account_name: str):
    """Stakeholder mapping: champions, blockers, decision-makers."""
    service = _require_service()
    results = await service.query_stakeholder_map(account_name)
    return {"success": True, "account_name": account_name, "stakeholders": results}


@app.get(
    "/api/accounts/{account_name}/intelligence/engagement-gaps",
    dependencies=[Depends(verify_api_key)],
)
async def get_engagement_gaps(account_name: str, days: int = 30):
    """Contacts not interacted with recently."""
    service = _require_service()
    results = await service.query_engagement_gaps(account_name, days_threshold=days)
    return {
        "success": True,
        "account_name": account_name,
        "gaps": results,
        "days_threshold": days,
    }


@app.get(
    "/api/accounts/{account_name}/intelligence/cross-branch",
    dependencies=[Depends(verify_api_key)],
)
async def get_cross_branch(account_name: str):
    """Cross-branch connections and shared opportunities."""
    service = _require_service()
    results = await service.query_cross_branch_connections(account_name)
    return {"success": True, "account_name": account_name, "branches": results}


@app.get(
    "/api/accounts/{account_name}/intelligence/opportunities",
    dependencies=[Depends(verify_api_key)],
)
async def get_opportunities(account_name: str):
    """Combined opportunity detection with stakeholder roles."""
    service = _require_service()
    results = await service.query_combined_opportunities(account_name)
    return {"success": True, "account_name": account_name, "opportunities": results}


# ============================================================
# Agent hooks — simplified flat payloads for CHAMP Mail etc.
# ============================================================


@app.post("/api/hooks/email", dependencies=[Depends(verify_api_key)])
async def hook_email(request: EmailHookRequest):
    """
    Simplified email ingestion for agent systems (CHAMP Mail, etc.).

    Flat payload — no mode/data nesting. Just the email fields.
    """
    service = _require_service()
    now = datetime.now(timezone.utc)

    content = f"""Email Communication Record
===========================
From: {request.from_address}
To: {request.to_address}
Subject: {request.subject}
Date: {now.strftime('%Y-%m-%d %H:%M:%S')}
Direction: {request.direction}
Account: {request.account_name}
Channel: email

Email Body:
-----------
{request.body[:8000]}
"""

    await service.ingest_episode(
        content=content,
        name=f"Email: {request.subject[:50]}",
        account_name=request.account_name,
        source_description=f"email ({request.direction})",
        reference_time=now,
    )

    return {
        "success": True,
        "message": f"Email '{request.subject[:50]}' logged to {request.account_name}",
    }


@app.post("/api/hooks/email/batch", dependencies=[Depends(verify_api_key)])
async def hook_email_batch(request: EmailHookBatchRequest):
    """Batch email ingestion — up to 100 emails at once."""
    service = _require_service()
    now = datetime.now(timezone.utc)

    episodes = []
    for email in request.emails:
        content = f"""Email Communication Record
===========================
From: {email.from_address}
To: {email.to_address}
Subject: {email.subject}
Date: {now.strftime('%Y-%m-%d %H:%M:%S')}
Direction: {email.direction}
Account: {email.account_name}
Channel: email

Email Body:
-----------
{email.body[:8000]}
"""
        episodes.append({
            "name": f"Email: {email.subject[:50]}",
            "content": content,
            "reference_time": now,
            "source_description": f"email ({email.direction})",
        })

    await service.ingest_episodes_bulk(episodes, request.account_name)

    return {
        "success": True,
        "message": f"Ingested {len(episodes)} emails to {request.account_name}",
        "episodes_ingested": len(episodes),
    }


@app.post("/api/hooks/call", dependencies=[Depends(verify_api_key)])
async def hook_call(request: CallHookRequest):
    """Simplified call ingestion for agent systems."""
    service = _require_service()
    now = datetime.now(timezone.utc)

    content = f"""Call Transcript Record
=======================
Caller: Our Team
Callee: {request.contact_name}
Date: {now.strftime('%Y-%m-%d %H:%M:%S')}
Duration: {request.duration_minutes} minutes
Direction: {request.direction}
Account: {request.account_name}

Summary: {request.summary}

Transcript:
-----------
{request.transcript[:8000] if request.transcript else 'No transcript available.'}
"""

    await service.ingest_episode(
        content=content,
        name=f"Call: {request.contact_name} - {request.summary[:50]}",
        account_name=request.account_name,
        source_description=f"call ({request.direction})",
        reference_time=now,
    )

    return {
        "success": True,
        "message": f"Call with {request.contact_name} logged to {request.account_name}",
    }


# ============================================================
# Email context — purpose-built for email composition agents
# ============================================================


@app.get(
    "/api/accounts/{account_name}/email-context",
    dependencies=[Depends(verify_api_key)],
)
async def get_email_context(
    account_name: str,
    contact_email: Optional[str] = None,
    contact_name: Optional[str] = None,
    subject: Optional[str] = None,
):
    """
    Get full context for composing an email follow-up.

    Purpose-built for CHAMP Mail and other email composition agents.
    Returns everything an agent needs to write a personalized,
    context-aware email.
    """
    service = _require_service()

    # Build a focused query based on available parameters
    query_parts = []
    if contact_name:
        query_parts.append(f"interactions with {contact_name}")
    if contact_email:
        query_parts.append(f"emails involving {contact_email}")
    if subject:
        query_parts.append(f"discussions about {subject}")
    if not query_parts:
        query_parts.append("recent email interactions and key contacts")

    focus_query = ", ".join(query_parts)

    # Gather all context in parallel-style (sequential but comprehensive)
    contact_results = await service.search_account(
        account_name, f"Who is {contact_name or contact_email or 'the contact'}? What is their role, title, and relationship?", 10
    )
    topic_results = await service.search_account(
        account_name, f"What topics were discussed regarding {focus_query}?", 10
    )
    timeline = await service.query_timeline(account_name, limit=10)
    personal = await service.query_personal_details(account_name)
    stakeholders = await service.query_stakeholder_map(account_name)

    # Filter timeline to email-only interactions involving the contact
    email_history = []
    for entry in timeline:
        is_email = entry.get("channel") == "email"
        mentions_contact = True  # Default include
        if contact_name:
            mentions_contact = contact_name.lower() in (entry.get("name", "") + (entry.get("summary", "") or "")).lower()
        if contact_email:
            mentions_contact = mentions_contact or contact_email.lower() in (entry.get("summary", "") or "").lower()
        if is_email and mentions_contact:
            email_history.append(entry)

    # Extract relevant facts
    facts = [
        e.get("fact") or e.get("summary") or e.get("name")
        for e in topic_results.get("edges", [])
        if e.get("fact") or e.get("summary")
    ]

    # Extract contact info
    contacts = [
        {"name": n["name"], "type": n["labels"][0] if n.get("labels") else "Unknown", "summary": n.get("summary")}
        for n in contact_results.get("nodes", [])
    ]

    # Personal details as strings
    personal_facts = [e.get("fact") for e in personal if e.get("fact")]

    return {
        "success": True,
        "account": account_name,
        "contact_name": contact_name,
        "contact_email": contact_email,
        "contacts": contacts,
        "email_history": email_history[:5],
        "all_interactions": timeline[:5],
        "topics_discussed": facts[:10],
        "personal_details": personal_facts,
        "stakeholders": [
            {"person": s["person"], "relationship": s["relationship"], "target": s["target"]}
            for s in stakeholders[:5]
        ],
    }


@app.get(
    "/api/accounts/{account_name}/briefing",
    dependencies=[Depends(verify_api_key)],
)
async def get_account_briefing(account_name: str):
    """
    Comprehensive pre-interaction briefing for an account.

    REST equivalent of the MCP get_briefing tool.
    """
    service = _require_service()

    contacts = await service.search_account(
        account_name, "Who are the contacts and people at this account?", 20
    )
    timeline = await service.query_timeline(account_name, limit=10)
    personal = await service.query_personal_details(account_name)
    stakeholders = await service.query_stakeholder_map(account_name)
    gaps = await service.query_engagement_gaps(account_name)

    return {
        "success": True,
        "account": account_name,
        "contacts": [
            {"name": n["name"], "summary": n.get("summary")}
            for n in contacts.get("nodes", [])
            if "Contact" in n.get("labels", [])
        ],
        "recent_interactions": timeline[:5],
        "personal_details": [e.get("fact") for e in personal if e.get("fact")],
        "stakeholders": stakeholders[:10],
        "stale_contacts": [g["contact_name"] for g in gaps],
    }


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8080"))

    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=True,
    )
