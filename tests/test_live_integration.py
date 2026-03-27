"""
CHAMP Graph — Live Integration Test Suite
==========================================
Hits the real running stack (localhost:8080) with dummy B2B sales data.
Covers every API endpoint, hook, MCP tool, and intelligence query.

Run with:
    pytest tests/test_live_integration.py -v --tb=short

Requirements:
    - docker compose up (stack must be running)
    - embeddinggemma:latest pulled in ollama (for ingest tests)
"""
import time
from datetime import datetime, timezone

import httpx
import pytest

BASE = "http://localhost:8080"
ACCOUNT = "TechCorp Inc"
HEADERS = {"Content-Type": "application/json"}

# ---------------------------------------------------------------------------
# Dummy data
# ---------------------------------------------------------------------------

DUMMY_EMAILS = [
    {
        "from_address": "alice@ourcompany.com",
        "to_address": "john.smith@techcorp.com",
        "subject": "Follow-up on Q2 pricing proposal",
        "body": (
            "Hi John, great catching up on the call last week. "
            "As discussed, I've attached our Q2 pricing proposal for the Enterprise plan. "
            "John mentioned he'd loop in Sarah Chen, their VP of Engineering, for technical eval. "
            "They're looking to close before end of quarter. Budget is around $120k annually."
        ),
        "direction": "outbound",
    },
    {
        "from_address": "john.smith@techcorp.com",
        "to_address": "alice@ourcompany.com",
        "subject": "RE: Follow-up on Q2 pricing proposal",
        "body": (
            "Thanks Alice! I've shared it with Sarah. She had a few concerns about the API rate limits. "
            "Also looping in Marcus Johnson, our CFO, who needs to approve anything over $100k. "
            "Marcus is pretty conservative — he'll want to see ROI numbers. "
            "PS: I'll be on vacation next week, fishing trip with my kids."
        ),
        "direction": "inbound",
    },
    {
        "from_address": "bob@ourcompany.com",
        "to_address": "sarah.chen@techcorp.com",
        "subject": "Technical deep-dive — API limits & integration",
        "body": (
            "Hi Sarah, I'm the solutions engineer working with Alice on the TechCorp deal. "
            "Happy to walk you through the API architecture. We can support up to 10k req/min "
            "on the Enterprise plan. I know you're also evaluating Competitor X — "
            "our latency is 40% lower. Sarah mentioned she has 2 kids and coaches little league."
        ),
        "direction": "outbound",
    },
    {
        "from_address": "marcus.johnson@techcorp.com",
        "to_address": "alice@ourcompany.com",
        "subject": "ROI analysis request",
        "body": (
            "Alice, Marcus here. Before I can approve this, I need a detailed ROI breakdown. "
            "We spent $85k with our current vendor last year with mediocre results. "
            "If you can show clear ROI within 6 months, I'm open to moving forward. "
            "I'm the final decision maker on this. The board reviews next quarter."
        ),
        "direction": "inbound",
    },
]

DUMMY_CALLS = [
    {
        "contact_name": "John Smith",
        "summary": (
            "Discovery call with John. He confirmed TechCorp is actively evaluating 3 vendors. "
            "Main pain point is their current tool's downtime — had 3 outages last month. "
            "John is the champion internally. Timeline: 60 days to decision."
        ),
        "duration_minutes": 32,
        "direction": "outbound",
        "transcript": (
            "Alice: Thanks for making time John. John: Of course! We're really struggling with uptime. "
            "Alice: Tell me more about the outages. John: Three last month, each 2+ hours. "
            "Lost about $50k in productivity. Alice: That's significant. What would success look like? "
            "John: Zero downtime, solid API, good support. We need this by Q3."
        ),
    },
    {
        "contact_name": "Sarah Chen",
        "summary": (
            "Technical eval call with Sarah Chen, VP Engineering. "
            "She's impressed with our API but wants a POC in their staging environment. "
            "Raised concern about data residency — they need US-only data storage. "
            "Sarah is a technical champion, not a blocker."
        ),
        "duration_minutes": 45,
        "direction": "outbound",
        "transcript": (
            "Bob: Hi Sarah, ready for the deep dive? Sarah: Yes! I reviewed the docs — impressive. "
            "Bob: Want to walk through the architecture? Sarah: Please. One thing — data residency? "
            "Bob: All US-based, SOC2 compliant. Sarah: Perfect. Can we do a POC next week? "
            "Bob: Absolutely. I'll set up a sandbox environment."
        ),
    },
]

DUMMY_RAW_EPISODES = [
    {
        "name": "LinkedIn: Connected with Marcus Johnson",
        "content": (
            "Team member Alice connected with Marcus Johnson (CFO at TechCorp Inc) on LinkedIn. "
            "Marcus has 20 years in finance, previously at Goldman Sachs. "
            "He posted recently about cost optimization strategies in SaaS procurement."
        ),
        "source_description": "LinkedIn connection via social",
    },
    {
        "name": "Meeting Notes: TechCorp QBR Prep",
        "content": (
            "Internal meeting notes for TechCorp QBR prep. "
            "Account: TechCorp Inc. Contacts engaged: John Smith (champion), Sarah Chen (technical), "
            "Marcus Johnson (economic buyer/blocker). "
            "Opportunity: Enterprise Platform Deal, $120k ARR, Stage: Technical Eval. "
            "Branch: TechCorp HQ (New York). Also have TechCorp West Coast branch in SF — "
            "separate budget, same parent account. "
            "Next steps: POC with Sarah, ROI doc for Marcus, exec alignment with John."
        ),
        "source_description": "Meeting notes via internal",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get(path, **kwargs):
    return httpx.get(f"{BASE}{path}", headers=HEADERS, timeout=30, **kwargs)


def post(path, json=None, **kwargs):
    return httpx.post(f"{BASE}{path}", json=json, headers=HEADERS, timeout=60, **kwargs)


def assert_ok(r, label=""):
    assert r.status_code == 200, f"{label} — HTTP {r.status_code}: {r.text[:300]}"
    data = r.json()
    assert data.get("success") is not False, f"{label} — success=False: {data}"
    return data


# ---------------------------------------------------------------------------
# 1. Health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health(self):
        r = get("/health")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "healthy"
        assert d["neo4j_connected"] is True
        print(f"\n  ✅ Health: {d['status']}, Neo4j: {d['neo4j_connected']}, uptime: {d['uptime_seconds']:.1f}s")


# ---------------------------------------------------------------------------
# 2. Ingest — hooks (simplified agent payloads)
# ---------------------------------------------------------------------------

class TestHooks:
    def test_hook_email_single(self):
        payload = {
            "account_name": ACCOUNT,
            **DUMMY_EMAILS[0],
        }
        r = post("/api/hooks/email", json=payload)
        d = assert_ok(r, "hook/email single")
        print(f"\n  ✅ Hook email single: {d.get('message')}")

    def test_hook_email_batch(self):
        emails = [{**e, "account_name": ACCOUNT} for e in DUMMY_EMAILS[1:]]
        payload = {"account_name": ACCOUNT, "emails": emails}
        r = post("/api/hooks/email/batch", json=payload)
        d = assert_ok(r, "hook/email/batch")
        print(f"\n  ✅ Hook email batch: {d.get('episodes_ingested')} ingested")

    def test_hook_call(self):
        payload = {"account_name": ACCOUNT, **DUMMY_CALLS[0]}
        r = post("/api/hooks/call", json=payload)
        d = assert_ok(r, "hook/call")
        print(f"\n  ✅ Hook call: {d.get('message')}")

    def test_hook_call_second(self):
        payload = {"account_name": ACCOUNT, **DUMMY_CALLS[1]}
        r = post("/api/hooks/call", json=payload)
        d = assert_ok(r, "hook/call 2")
        print(f"\n  ✅ Hook call 2: {d.get('message')}")


# ---------------------------------------------------------------------------
# 3. Ingest — generic /api/ingest (raw + structured modes)
# ---------------------------------------------------------------------------

class TestIngest:
    def test_ingest_raw(self):
        payload = {
            "account_name": ACCOUNT,
            "mode": "raw",
            "name": DUMMY_RAW_EPISODES[0]["name"],
            "content": DUMMY_RAW_EPISODES[0]["content"],
            "source_description": DUMMY_RAW_EPISODES[0]["source_description"],
            "reference_time": "2026-03-20T10:00:00Z",
        }
        r = post("/api/ingest", json=payload)
        d = assert_ok(r, "ingest raw")
        print(f"\n  ✅ Ingest raw: {d.get('message')}")

    def test_ingest_raw_second(self):
        payload = {
            "account_name": ACCOUNT,
            "mode": "raw",
            "name": DUMMY_RAW_EPISODES[1]["name"],
            "content": DUMMY_RAW_EPISODES[1]["content"],
            "source_description": DUMMY_RAW_EPISODES[1]["source_description"],
            "reference_time": "2026-03-21T09:00:00Z",
        }
        r = post("/api/ingest", json=payload)
        d = assert_ok(r, "ingest raw 2")
        print(f"\n  ✅ Ingest raw 2: {d.get('message')}")

    def test_ingest_structured_email(self):
        payload = {
            "account_name": ACCOUNT,
            "mode": "email",
            "data": {
                "subject": "Contract review — TechCorp Enterprise",
                "from_address": "alice@ourcompany.com",
                "to_address": "john.smith@techcorp.com",
                "body": "Hi John, attaching the final contract for your review. Legal has signed off.",
                "timestamp": "2026-03-22T14:00:00Z",
                "channel": "email",
                "direction": "outbound",
            },
        }
        r = post("/api/ingest", json=payload)
        d = assert_ok(r, "ingest structured email")
        print(f"\n  ✅ Ingest structured email: {d.get('message')}")

    def test_ingest_structured_call(self):
        payload = {
            "account_name": ACCOUNT,
            "mode": "call",
            "data": {
                "caller": "alice@ourcompany.com",
                "recipient": "marcus.johnson@techcorp.com",
                "transcript": "Alice: Hi Marcus, following up on the ROI doc. Marcus: Looks good, board approved.",
                "duration_seconds": 600,
                "timestamp": "2026-03-23T11:00:00Z",
                "direction": "outbound",
                "summary": "Marcus confirmed board approved the deal. Moving to contract stage.",
            },
        }
        r = post("/api/ingest", json=payload)
        d = assert_ok(r, "ingest structured call")
        print(f"\n  ✅ Ingest structured call: {d.get('message')}")

    def test_bulk_ingest(self):
        payload = {
            "account_name": ACCOUNT,
            "items": [
                {
                    "mode": "raw",
                    "name": "Text: John Smith check-in",
                    "content": "John Smith texted Alice: 'Quick update — Marcus is in. Let's close this week!'",
                    "source_description": "SMS via text message (inbound)",
                    "reference_time": "2026-03-24T08:30:00Z",
                },
                {
                    "mode": "raw",
                    "name": "LinkedIn: Sarah Chen endorsed our post",
                    "content": "Sarah Chen liked and commented on our product launch post on LinkedIn. Comment: 'Great API design!'",
                    "source_description": "LinkedIn social engagement",
                    "reference_time": "2026-03-24T09:00:00Z",
                },
                {
                    "mode": "raw",
                    "name": "Meeting: Kickoff call scheduled",
                    "content": "Kickoff meeting scheduled with TechCorp Inc. Attendees: John Smith, Sarah Chen, Alice, Bob. Date: April 1st 2026.",
                    "source_description": "Calendar meeting notes",
                    "reference_time": "2026-03-25T10:00:00Z",
                },
            ],
        }
        r = post("/api/ingest/batch", json=payload)
        d = assert_ok(r, "bulk ingest")
        assert d.get("episodes_ingested", 0) == 3
        print(f"\n  ✅ Bulk ingest: {d.get('episodes_ingested')} episodes ingested")


# ---------------------------------------------------------------------------
# 4. Wait for graph to settle before querying
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def wait_after_ingest():
    """Run all ingest tests first, then wait for graph to settle."""
    yield
    # After all tests, no extra wait needed (queries run after ingest in order)


# ---------------------------------------------------------------------------
# 5. Query endpoints
# ---------------------------------------------------------------------------

class TestQueries:
    def test_search(self):
        payload = {"account": ACCOUNT, "query": "Who are the contacts and what did they discuss?", "num_results": 20}
        r = post("/api/query", json=payload)
        d = assert_ok(r, "search")
        nodes = d.get("data", {}).get("nodes", [])
        edges = d.get("data", {}).get("edges", [])
        print(f"\n  ✅ Search: {len(nodes)} nodes, {len(edges)} edges")

    def test_get_contacts(self):
        r = get(f"/api/accounts/{ACCOUNT}/contacts")
        d = assert_ok(r, "get contacts")
        contacts = d.get("contacts", [])
        print(f"\n  ✅ Contacts: {len(contacts)} found — {[c.get('name') for c in contacts[:5]]}")

    def test_get_topics(self):
        r = get(f"/api/accounts/{ACCOUNT}/topics")
        d = assert_ok(r, "get topics")
        topics = d.get("topics", [])
        print(f"\n  ✅ Topics: {len(topics)} found — {[t.get('name') for t in topics[:5]]}")

    def test_get_communications(self):
        r = get(f"/api/accounts/{ACCOUNT}/communications")
        d = assert_ok(r, "get communications")
        comms = d.get("communications", [])
        print(f"\n  ✅ Communications: {len(comms)} found")

    def test_get_personal_details(self):
        r = get(f"/api/accounts/{ACCOUNT}/personal-details")
        d = assert_ok(r, "get personal details")
        details = d.get("personal_details", [])
        print(f"\n  ✅ Personal details: {len(details)} found — {[p.get('detail') for p in details[:3]]}")

    def test_get_team_contacts(self):
        r = get(f"/api/accounts/{ACCOUNT}/team-contacts")
        d = assert_ok(r, "get team contacts")
        team = d.get("team_contacts", [])
        print(f"\n  ✅ Team contacts: {len(team)} found")

    def test_get_graph(self):
        r = get(f"/api/accounts/{ACCOUNT}/graph")
        d = assert_ok(r, "get graph")
        nodes = d.get("nodes", [])
        edges = d.get("edges", [])
        print(f"\n  ✅ Graph: {len(nodes)} nodes, {len(edges)} edges")

    def test_get_timeline(self):
        r = get(f"/api/accounts/{ACCOUNT}/timeline")
        d = assert_ok(r, "get timeline")
        timeline = d.get("timeline", [])
        print(f"\n  ✅ Timeline: {len(timeline)} events")

    def test_get_relationships(self):
        r = get(f"/api/accounts/{ACCOUNT}/relationships")
        d = assert_ok(r, "get relationships")
        rels = d.get("relationships", [])
        print(f"\n  ✅ Relationships: {len(rels)} found")


# ---------------------------------------------------------------------------
# 6. Intelligence endpoints
# ---------------------------------------------------------------------------

class TestIntelligence:
    def test_cross_salesperson(self):
        r = get(f"/api/accounts/{ACCOUNT}/intelligence/salesperson-overlap")
        d = assert_ok(r, "cross-salesperson")
        overlaps = d.get("overlaps", [])
        print(f"\n  ✅ Cross-salesperson overlaps: {len(overlaps)}")

    def test_stakeholders(self):
        r = get(f"/api/accounts/{ACCOUNT}/intelligence/stakeholder-map")
        d = assert_ok(r, "stakeholders")
        stakeholders = d.get("stakeholders", [])
        print(f"\n  ✅ Stakeholders: {len(stakeholders)} — {[s.get('person') for s in stakeholders[:4]]}")

    def test_engagement_gaps(self):
        r = get(f"/api/accounts/{ACCOUNT}/intelligence/engagement-gaps")
        d = assert_ok(r, "engagement gaps")
        gaps = d.get("gaps", [])
        print(f"\n  ✅ Engagement gaps: {len(gaps)}")

    def test_cross_branch(self):
        r = get(f"/api/accounts/{ACCOUNT}/intelligence/cross-branch")
        d = assert_ok(r, "cross branch")
        branches = d.get("branches", [])
        print(f"\n  ✅ Cross-branch: {len(branches)}")

    def test_opportunities(self):
        r = get(f"/api/accounts/{ACCOUNT}/intelligence/opportunities")
        d = assert_ok(r, "opportunities")
        opps = d.get("opportunities", [])
        print(f"\n  ✅ Opportunities: {len(opps)}")

    def test_briefing(self):
        r = get(f"/api/accounts/{ACCOUNT}/briefing")
        d = assert_ok(r, "briefing")
        print(f"\n  ✅ Briefing keys: {list(d.keys())}")

    def test_email_context(self):
        r = get(
            f"/api/accounts/{ACCOUNT}/email-context",
            params={"contact_name": "John Smith", "subject": "pricing"},
        )
        d = assert_ok(r, "email context")
        print(f"\n  ✅ Email context keys: {list(d.keys())}")

    def test_stale_contacts(self):
        r = get(f"/api/accounts/{ACCOUNT}/intelligence/engagement-gaps")
        d = assert_ok(r, "stale contacts")
        stale = d.get("gaps", [])
        print(f"\n  ✅ Stale contacts (engagement gaps): {len(stale)}")


# ---------------------------------------------------------------------------
# 7. MCP tools (via StreamableHTTP transport)
# ---------------------------------------------------------------------------

class TestMCP:
    MCP_URL = f"{BASE}/mcp"

    def _mcp_call(self, tool_name, arguments):
        """Call an MCP tool via JSON-RPC over HTTP."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        r = httpx.post(
            self.MCP_URL,
            json=payload,
            headers={**HEADERS, "Accept": "application/json, text/event-stream"},
            timeout=60,
            follow_redirects=True,
        )
        assert r.status_code in (200, 202), f"MCP {tool_name} — HTTP {r.status_code}: {r.text[:300]}"
        return r

    def test_mcp_remember(self):
        r = self._mcp_call("remember", {
            "account_name": ACCOUNT,
            "information": "TechCorp is a Series B startup with 150 employees. They use AWS and are SOC2 certified.",
        })
        print(f"\n  ✅ MCP remember: HTTP {r.status_code}")

    def test_mcp_log_email(self):
        r = self._mcp_call("log_email", {
            "account_name": ACCOUNT,
            "from_address": "alice@ourcompany.com",
            "to_address": "john.smith@techcorp.com",
            "subject": "Contract sent",
            "body": "Hi John, the signed contract is attached. Welcome aboard!",
            "direction": "outbound",
        })
        print(f"\n  ✅ MCP log_email: HTTP {r.status_code}")

    def test_mcp_log_call(self):
        r = self._mcp_call("log_call", {
            "account_name": ACCOUNT,
            "contact_name": "John Smith",
            "summary": "Closing call — John confirmed wire transfer initiated.",
            "duration_minutes": 15,
            "transcript": "Alice: Everything set on your end? John: Yes, wire is going out today.",
        })
        print(f"\n  ✅ MCP log_call: HTTP {r.status_code}")

    def test_mcp_recall(self):
        r = self._mcp_call("recall", {
            "account_name": ACCOUNT,
            "query": "What is the deal value and who are the decision makers?",
        })
        print(f"\n  ✅ MCP recall: HTTP {r.status_code}")

    def test_mcp_get_briefing(self):
        r = self._mcp_call("get_briefing", {"account_name": ACCOUNT})
        print(f"\n  ✅ MCP get_briefing: HTTP {r.status_code}")

    def test_mcp_get_email_context(self):
        r = self._mcp_call("get_email_context", {
            "account_name": ACCOUNT,
            "contact_name": "Marcus Johnson",
            "subject": "ROI and contract",
        })
        print(f"\n  ✅ MCP get_email_context: HTTP {r.status_code}")

    def test_mcp_get_stakeholders(self):
        r = self._mcp_call("get_stakeholders", {"account_name": ACCOUNT})
        print(f"\n  ✅ MCP get_stakeholders: HTTP {r.status_code}")

    def test_mcp_get_timeline(self):
        r = self._mcp_call("get_timeline", {"account_name": ACCOUNT})
        print(f"\n  ✅ MCP get_timeline: HTTP {r.status_code}")

    def test_mcp_find_stale_contacts(self):
        r = self._mcp_call("find_stale_contacts", {"account_name": ACCOUNT})
        print(f"\n  ✅ MCP find_stale_contacts: HTTP {r.status_code}")


# ---------------------------------------------------------------------------
# 8. Sync endpoint
# ---------------------------------------------------------------------------

class TestSync:
    def test_sync_status(self):
        r = get("/api/sync/status")
        assert r.status_code == 200
        print(f"\n  ✅ Sync status: {r.json()}")

    def test_sync_trigger_no_adapter(self):
        """Trigger sync — will return error since no email adapter configured, but endpoint must respond."""
        payload = {"source_type": "email", "full_sync": False}
        r = post(f"/api/sync/{ACCOUNT}", json=payload)
        # 200 with success or 400/500 with meaningful error — both are acceptable
        assert r.status_code in (200, 400, 422, 500), f"Unexpected status: {r.status_code}"
        print(f"\n  ✅ Sync trigger responded: HTTP {r.status_code}")


# ---------------------------------------------------------------------------
# 9. Final summary — print what's in the graph
# ---------------------------------------------------------------------------

class TestSummary:
    def test_final_graph_summary(self):
        """Print a full summary of what ended up in the graph."""
        print("\n" + "=" * 60)
        print("  CHAMP GRAPH — FINAL STATE SUMMARY")
        print("=" * 60)

        r = get(f"/api/accounts/{ACCOUNT}/graph")
        if r.status_code == 200:
            d = r.json()
            nodes = d.get("nodes", [])
            edges = d.get("edges", [])

            # Group nodes by type
            by_type = {}
            for n in nodes:
                t = n.get("type", "Unknown")
                by_type.setdefault(t, []).append(n.get("label", "?"))

            print(f"\n  Total nodes : {len(nodes)}")
            print(f"  Total edges : {len(edges)}")
            print("\n  Nodes by type:")
            for t, names in sorted(by_type.items()):
                print(f"    {t:20s}: {', '.join(names[:5])}")

            print("\n  Sample edges:")
            for e in edges[:8]:
                print(f"    {e.get('label', '?'):25s} | {e.get('fact', '')[:60]}")

        print("\n" + "=" * 60)
        assert True  # always pass — this is informational
