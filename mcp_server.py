"""
CHAMP Graph MCP Server

Exposes the knowledge graph as MCP tools for AI agents.
Tools are verb-oriented and agent-friendly — designed for LLM consumption,
not REST endpoint mirrors.

Mount on the existing FastAPI app via:
    app.mount("/mcp", mcp.http_app())
"""
import logging
from datetime import datetime, timezone
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def _get_service():
    """Get the shared GraphitiService instance from api_server."""
    from api_server import graphiti_service

    if not graphiti_service:
        raise RuntimeError("CHAMP Graph service not initialized")
    return graphiti_service


mcp = FastMCP(
    "champ-graph",
    instructions=(
        "Knowledge graph memory for B2B sales. Store and retrieve "
        "information about accounts, contacts, calls, emails, and deals. "
        "The graph automatically extracts entities (contacts, topics, "
        "opportunities) and relationships from any text you store."
    ),
)


# ============================================================
# Write tools — push data into the graph
# ============================================================


@mcp.tool()
async def remember(
    account_name: str,
    content: str,
    source: str = "agent",
    name: str = "Agent note",
) -> dict:
    """Store a piece of information about an account in the knowledge graph.

    Use this after calls, emails, meetings, or any interaction with a prospect.
    The system will automatically extract contacts, topics, relationships,
    and other entities from the content.

    Args:
        account_name: The company/account name (e.g., "Acme Corp")
        content: The information to store — can be a call summary, email body,
                 meeting notes, or any free-form text about the interaction
        source: What produced this information (e.g., "voice_agent", "email_agent")
        name: A short label for this entry (e.g., "Call with John re: pricing")
    """
    service = _get_service()
    await service.ingest_episode(
        content=content,
        name=name,
        account_name=account_name,
        source_description=f"Agent ingestion ({source})",
        reference_time=datetime.now(timezone.utc),
    )
    return {
        "success": True,
        "message": f"Stored to {account_name}",
        "account_name": account_name,
    }


@mcp.tool()
async def log_call(
    account_name: str,
    contact_name: str,
    summary: str,
    duration_minutes: int = 0,
    direction: str = "outbound",
    transcript: str = "",
) -> dict:
    """Log a completed call with a prospect.

    The system will automatically extract contacts, topics, relationships,
    and sentiment from the call content.

    Args:
        account_name: The company/account (e.g., "Acme Corp")
        contact_name: Who the call was with (e.g., "John Smith")
        summary: Brief summary of what was discussed
        duration_minutes: How long the call lasted
        direction: "outbound" if we called them, "inbound" if they called us
        transcript: Full call transcript if available (optional)
    """
    service = _get_service()
    now = datetime.now(timezone.utc)

    content = f"""Call Transcript Record
=======================
Caller: Our Team
Callee: {contact_name}
Date: {now.strftime('%Y-%m-%d %H:%M:%S')}
Duration: {duration_minutes} minutes
Direction: {direction}
Account: {account_name}

Summary: {summary}

Transcript:
-----------
{transcript[:8000] if transcript else 'No transcript available.'}
"""

    await service.ingest_episode(
        content=content,
        name=f"Call: {contact_name} - {summary[:50]}",
        account_name=account_name,
        source_description=f"call ({direction})",
        reference_time=now,
    )
    return {
        "success": True,
        "message": f"Call with {contact_name} logged to {account_name}",
    }


@mcp.tool()
async def log_email(
    account_name: str,
    from_address: str,
    to_address: str,
    subject: str,
    body: str,
    direction: str = "outbound",
) -> dict:
    """Log an email interaction with a prospect.

    Args:
        account_name: The company/account
        from_address: Sender email address
        to_address: Recipient email address
        subject: Email subject line
        body: Email body text
        direction: "outbound" if we sent it, "inbound" if we received it
    """
    service = _get_service()
    now = datetime.now(timezone.utc)

    content = f"""Email Communication Record
===========================
From: {from_address}
To: {to_address}
Subject: {subject}
Date: {now.strftime('%Y-%m-%d %H:%M:%S')}
Direction: {direction}
Account: {account_name}
Channel: email

Email Body:
-----------
{body[:8000]}
"""

    await service.ingest_episode(
        content=content,
        name=f"Email: {subject[:50]}",
        account_name=account_name,
        source_description=f"email ({direction})",
        reference_time=now,
    )
    return {
        "success": True,
        "message": f"Email '{subject[:50]}' logged to {account_name}",
    }


# ============================================================
# Read tools — pull data from the graph
# ============================================================


@mcp.tool()
async def recall(
    account_name: str,
    query: str,
    num_results: int = 10,
) -> dict:
    """Search the knowledge graph for information about an account.

    Ask natural language questions like:
    - "Who are the decision makers at this account?"
    - "What topics did we discuss in the last meeting?"
    - "What personal details do we know about John?"
    - "What is the org structure?"

    Args:
        account_name: The company/account name to search within
        query: Natural language question about the account
        num_results: Max results to return (default 10)
    """
    service = _get_service()
    results = await service.search_account(account_name, query, num_results)

    return {
        "account": account_name,
        "facts": [
            e.get("fact") or e.get("summary") or e.get("name")
            for e in results.get("edges", [])
            if e.get("fact") or e.get("summary")
        ],
        "entities": [
            {
                "name": n["name"],
                "type": n["labels"][0] if n.get("labels") else "Unknown",
                "summary": n.get("summary"),
            }
            for n in results.get("nodes", [])
        ],
    }


@mcp.tool()
async def get_briefing(account_name: str) -> dict:
    """Get a comprehensive pre-call or pre-email briefing for an account.

    Returns key contacts, recent interactions, personal details about contacts,
    open opportunities, stakeholder roles, and engagement gaps.

    Use this before reaching out to any contact at the account.

    Args:
        account_name: The company/account name
    """
    service = _get_service()

    contacts = await service.search_account(
        account_name, "Who are the contacts and people at this account?", 20
    )
    timeline = await service.query_timeline(account_name, limit=10)
    personal = await service.query_personal_details(account_name)
    stakeholders = await service.query_stakeholder_map(account_name)
    gaps = await service.query_engagement_gaps(account_name)

    return {
        "account": account_name,
        "contacts": [
            {"name": n["name"], "summary": n.get("summary")}
            for n in contacts.get("nodes", [])
            if "Contact" in n.get("labels", [])
        ],
        "recent_interactions": timeline[:5],
        "personal_details": [
            e.get("fact") for e in personal if e.get("fact")
        ],
        "stakeholders": stakeholders[:10],
        "stale_contacts": [g["contact_name"] for g in gaps],
    }


@mcp.tool()
async def get_email_context(
    account_name: str,
    contact_email: str = "",
    contact_name: str = "",
    subject: str = "",
) -> dict:
    """Get full context for composing an email reply or follow-up.

    Use this before writing any email. Returns the interaction history,
    personal details, topics discussed, and stakeholder info needed to
    write a personalized, context-aware message.

    Args:
        account_name: The company/account name
        contact_email: Email address of the person you're emailing (optional)
        contact_name: Name of the person you're emailing (optional)
        subject: Subject or topic of the email for focused context (optional)
    """
    service = _get_service()

    # Build focused query
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
    identifier = contact_name or contact_email or "the contact"

    contact_results = await service.search_account(
        account_name,
        f"Who is {identifier}? What is their role, title, and relationship?",
        10,
    )
    topic_results = await service.search_account(
        account_name,
        f"What topics were discussed regarding {focus_query}?",
        10,
    )
    timeline = await service.query_timeline(account_name, limit=10)
    personal = await service.query_personal_details(account_name)
    stakeholders = await service.query_stakeholder_map(account_name)

    # Filter to email interactions involving the contact
    email_history = []
    for entry in timeline:
        if entry.get("channel") != "email":
            continue
        searchable = (entry.get("name", "") + (entry.get("summary", "") or "")).lower()
        if contact_name and contact_name.lower() in searchable:
            email_history.append(entry)
        elif contact_email and contact_email.lower() in (entry.get("summary", "") or "").lower():
            email_history.append(entry)
        elif not contact_name and not contact_email:
            email_history.append(entry)

    return {
        "account": account_name,
        "contact_name": contact_name or None,
        "contact_email": contact_email or None,
        "contacts": [
            {
                "name": n["name"],
                "type": n["labels"][0] if n.get("labels") else "Unknown",
                "summary": n.get("summary"),
            }
            for n in contact_results.get("nodes", [])
        ],
        "email_history": email_history[:5],
        "all_interactions": timeline[:5],
        "topics_discussed": [
            e.get("fact") or e.get("summary") or e.get("name")
            for e in topic_results.get("edges", [])
            if e.get("fact") or e.get("summary")
        ][:10],
        "personal_details": [
            e.get("fact") for e in personal if e.get("fact")
        ],
        "stakeholders": [
            {"person": s["person"], "relationship": s["relationship"], "target": s["target"]}
            for s in stakeholders[:5]
        ],
    }


@mcp.tool()
async def get_stakeholders(account_name: str) -> dict:
    """Get the stakeholder map for an account.

    Returns champions, blockers, decision-makers, and their roles
    in active opportunities.

    Args:
        account_name: The company/account name
    """
    service = _get_service()
    stakeholders = await service.query_stakeholder_map(account_name)
    opportunities = await service.query_combined_opportunities(account_name)

    return {
        "account": account_name,
        "stakeholders": stakeholders,
        "opportunities": opportunities,
    }


@mcp.tool()
async def get_timeline(account_name: str, limit: int = 20) -> dict:
    """Get the recent interaction timeline for an account.

    Returns a chronological list of all interactions (emails, calls, meetings,
    texts, social) with this account.

    Args:
        account_name: The company/account name
        limit: Max number of interactions to return (default 20)
    """
    service = _get_service()
    timeline = await service.query_timeline(account_name, limit=limit)

    return {
        "account": account_name,
        "timeline": timeline,
        "total": len(timeline),
    }


@mcp.tool()
async def find_stale_contacts(account_name: str, days: int = 30) -> dict:
    """Find contacts at an account who haven't been contacted recently.

    Use this to identify engagement gaps and follow-up opportunities.

    Args:
        account_name: The company/account name
        days: Number of days without contact to consider "stale" (default 30)
    """
    service = _get_service()
    gaps = await service.query_engagement_gaps(account_name, days_threshold=days)

    return {
        "account": account_name,
        "stale_contacts": gaps,
        "days_threshold": days,
        "total": len(gaps),
    }
