# CHAMP Graph

**Centralized High-context Agent Memory Platform**

CHAMP Graph is a plug-and-play temporal knowledge graph system that serves as the centralized memory layer for AI agents. It ingests multi-modal communication data (emails, calls, texts, meetings, LinkedIn) and builds a unified, queryable knowledge graph specifically tuned for prospect and company intelligence in B2B sales.

**This is NOT an agent system.** This is the knowledge/memory layer that agents plug into. The agents are built separately and consume CHAMP Graph via its REST API, MCP server, or Python SDK.

**Four Pillars:**
1. **Multi-modal context centralization** — All channels (email, calls, SMS, social platforms, meetings) feed into one unified graph
2. **Cross-agent continuity** — Any agent can pick up where another left off with full context across channels
3. **Company-centric graph topology** — Account nodes are the hub; all contacts, communications, and opportunities link through them. Cross-branch and cross-salesperson relationships are first-class citizens
4. **Self-enriching** — The graph grows and refines itself as data flows in, surfacing edge-case relations and combined opportunities without manual curation

---

## Architecture

```
Data Sources (Email, Calls, SMS, LinkedIn, Meetings)
        |
        v
  [Adapters]  ── Normalize raw data into Pydantic models
        |
        v
  [SyncService]  ── Batch orchestration, dedup, ordering
        |
        v
  [GraphitiService]  ── Graphiti Core wrapper (LLM extraction)
        |
        v
  [Neo4j]  ── Temporal knowledge graph storage
        |
        v
  [FastAPI Server :8080]  ── REST endpoints + hook endpoints for agents
        |
        ├── [MCP Server /mcp]  ── 9 tools, auto-discovered by MCP-compatible agents
        ├── [REST API /api]    ── Direct HTTP for server-to-server integration
        ├── [Python SDK]       ── GraffitiClient for Python agent systems
        v
  [External Agents / Visualization]
```

**Layer responsibilities:**
- **Adapters** (`adapters/`): Provider-specific. Connect to source, fetch raw data, normalize into Pydantic models. No business logic.
- **Models** (`models/`): Pydantic models for normalized data. Every model implements `to_episode_content() -> str`.
- **Config** (`config/`): Graph schema (entity types, edge types, EDGE_TYPE_MAP), account definitions, env settings.
- **Services** (`services/`): Business logic. `GraphitiService` wraps graphiti-core. `SyncService` orchestrates ingestion.
- **API** (`api/` + `api_server.py`): FastAPI with lifespan management. `api/auth.py` for X-API-Key middleware. `api/models.py` for request/response models. `api/ingest_helpers.py` for dual-mode ingestion resolution. Standardized JSON responses for any agent client. Hook endpoints under `/api/hooks/` for simplified agent payloads.
- **MCP** (`mcp_server.py`): FastMCP server mounted at `/mcp`. 9 verb-oriented tools for agent discovery. No auth (inherits from transport).
- **SDK** (`sdk/`): `GraffitiClient` async HTTP client. Wraps REST API with retry, error handling, typed methods. For Python agent systems to import directly.
- **Visualization** (`visualization/`): D3.js interactive graph viewer.

---

## Tech Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| Graph Engine | graphiti-core | >=0.24.0, handles semantic search + graph management |
| Graph DB | Neo4j | 5.26.2+ via Docker |
| LLM | OpenRouter (OpenAI-compatible) | Default: `anthropic/claude-sonnet-4` |
| API | FastAPI + Uvicorn | Port 8080 |
| Data Validation | Pydantic v2 + pydantic-settings | |
| HTTP Client | httpx (async) | For MS Graph, future APIs |
| Python | 3.10+ | async/await throughout |

All LLM calls go through OpenRouter, configured via `OPENAI_BASE_URL`. The system is model-agnostic — any OpenAI-compatible endpoint works.

---

## Graph Schema

### Entity Types (Nodes)

Defined in `config/entity_types.py`. These Pydantic models guide LLM extraction.

| Entity | Required Fields | Optional Fields | Purpose |
|--------|----------------|-----------------|---------|
| **Contact** | `name` | `email`, `title`, `department` | Person at a target account |
| **Account** | `name` | `domain`, `industry` | Target company/MQA |
| **TeamMember** | `name` | `email`, `role` | Internal team (SDR, AE, CSM) |
| **PersonalDetail** | `category`, `detail` | — | Personal tidbits (family, hobbies, interests) |
| **Topic** | `name` | `category` | Discussion subject (pricing, product, support) |
| **Communication** | `channel`, `direction` | `sentiment` | Interaction event with metadata |
| **Opportunity** | `name` | `stage`, `value` | Sales opportunity or deal |
| **Branch** | `name` | `location`, `parent_account` | Branch/division of an account for cross-branch discovery |

### Edge Types (Relationships)

Defined in `config/edge_types.py`. The `EDGE_TYPE_MAP` constrains which edges can connect which node types — always update it when adding new edges.

| Edge | Source → Target | Properties |
|------|----------------|------------|
| `SENT_EMAIL_TO` | TeamMember ↔ Contact | `subject` |
| `WORKS_AT` | Contact → Account | `title`, `department` |
| `REPORTS_TO` | Contact → Contact | `relationship` |
| `HAS_PERSONAL_DETAIL` | Contact → PersonalDetail | `mentioned_date` |
| `DISCUSSED_TOPIC` | Contact/TeamMember/Communication → Topic | `context` |
| `RESPONDED_VIA` | Contact → Communication | `response_time_hours` |
| `INTERESTED_IN` | Contact → Topic | `level` (high/medium/low) |
| `MENTIONED_BY` | Any → Contact | `sentiment` |
| `CALLED` | TeamMember ↔ Contact | `duration_minutes`, `summary` |
| `TEXTED` | TeamMember ↔ Contact | `message_preview` |
| `MET_WITH` | TeamMember ↔ Contact | `meeting_type`, `attendees_count` |
| `CONNECTED_ON` | TeamMember ↔ Contact | `platform` |
| `BELONGS_TO_BRANCH` | Contact/Branch → Branch/Account | `primary` |
| `COVERS_ACCOUNT` | TeamMember → Account | `territory`, `primary` |
| `HAS_OPPORTUNITY` | Account → Opportunity | `created_date` |
| `INVOLVED_IN` | Contact/TeamMember → Opportunity | `role` (champion, blocker, etc.) |

---

## Project Structure

```
CHAMP-Graph/
├── CLAUDE.md                  # This file — project bible
├── api_server.py              # FastAPI server (port 8080)
├── requirements.txt           # Python dependencies
├── .env.example               # Environment template
├── Dockerfile                 # Python 3.11-slim container
├── docker-compose.yml         # Neo4j + CHAMP Graph
├── railway.toml               # Railway deployment config
├── .dockerignore              # Docker build exclusions
├── test_setup.py              # Setup verification tests
├── setup_gmail_oauth.py       # Gmail OAuth setup wizard
│
├── api/                       # API layer
│   ├── auth.py                # X-API-Key middleware (verify_api_key dependency)
│   ├── models.py              # All request/response Pydantic models
│   └── ingest_helpers.py      # IngestMode → episode content resolution
│
├── adapters/                  # Data source adapters
│   ├── base_adapter.py        # BaseAdapter (generic) + BaseEmailAdapter (email-specific)
│   ├── gmail_adapter.py       # Gmail/Google Workspace
│   └── outlook_adapter.py     # Microsoft 365/Outlook
│
├── config/                    # Configuration & graph schema
│   ├── settings.py            # Pydantic BaseSettings (env vars) + api_key field
│   ├── entity_types.py        # Node type definitions + ENTITY_TYPES dict (8 types)
│   ├── edge_types.py          # Edge type definitions + EDGE_TYPE_MAP (16 types)
│   └── accounts.py            # Target account configs
│
├── models/                    # Normalized data models
│   ├── base.py                # CommunicationDirection enum (shared)
│   ├── email.py               # Email model
│   ├── call_transcript.py     # CallTranscript model
│   ├── text_message.py        # TextMessage model
│   ├── social_engagement.py   # SocialEngagement model (LinkedIn, Twitter, etc.)
│   └── meeting_notes.py       # MeetingNotes model
│
├── services/                  # Business logic
│   ├── graphiti_service.py    # Graphiti Core wrapper (generic + email ingest, search, query, intelligence)
│   ├── sync_service.py        # Email sync orchestration
│   └── multi_sync_service.py  # Multi-source SyncService with adapter registry
│
├── mcp_server.py              # MCP server (9 tools, mounted at /mcp)
│
├── sdk/                       # Python SDK for external agent integration
│   ├── __init__.py            # Exports GraffitiClient
│   └── graffiti_client.py     # Async HTTP client with retry logic
│
├── tests/                     # Test suite (144 tests)
│   ├── conftest.py            # Shared fixtures (mock service, api_key)
│   ├── test_models.py         # Data model tests
│   ├── test_ingest_helpers.py # resolve_episode() tests
│   ├── test_api_auth.py       # Auth middleware tests
│   ├── test_api_ingest.py     # Ingest endpoint tests
│   ├── test_api_queries.py    # Query + intelligence endpoint tests
│   ├── test_sync_service.py   # SyncService tests
│   ├── test_mcp_server.py     # MCP tool tests (8 original tools)
│   ├── test_mcp_email_context.py # MCP get_email_context tool tests
│   ├── test_hooks.py          # Webhook hook endpoint tests
│   ├── test_email_context.py  # Email context + briefing endpoint tests
│   └── test_sdk.py            # GraffitiClient SDK tests
│
└── visualization/             # Graph viewer
    └── index.html             # D3.js interactive visualization
```

---

## Design Principles

1. **Adapter-agnostic ingestion.** The graph service accepts normalized Pydantic models, never raw provider data. Adding a new data source means: create adapter, create model, wire through SyncService. The graph layer never changes.

2. **Graph-first, not source-first.** Data is stored as entities and relationships, not documents. An email is decomposed into Contact nodes, Topic nodes, Communication edges. The original source is an episode (ephemeral); the extracted knowledge is permanent.

3. **Temporal awareness.** Graphiti-core tracks `valid_at`/`invalid_at` on edges. Relationships can expire. Always set `reference_time` on every episode for correct temporal ordering.

4. **Company-centric topology.** The Account node is the hub. All Contacts connect via `WORKS_AT`. All Communications connect Contacts to TeamMembers. This enables "give me everything about Company X" queries through a single `group_id`.

5. **Self-enriching.** Every new piece of data may update existing entities (Graphiti handles dedup and merge). Never create ingestion paths that bypass Graphiti's entity resolution.

6. **Agent-agnostic API.** The API serves any client. No agent-specific logic in services or endpoints. If an agent needs a special query, add a pre-built query method to `GraphitiService`, not a custom endpoint.

7. **Batch over single.** Prefer `ingest_episodes_bulk()` / `ingest_emails_bulk()` over single-episode methods. Graphiti's `add_episode_bulk()` is significantly more efficient.

---

## Coding Conventions

**Python:**
- Python 3.10+ with full type hints on all function signatures
- Use `Optional[X]` for optional fields
- Logging via `logging.getLogger(__name__)` — no print statements in library code
- Module files begin with a docstring explaining purpose

**Async:**
- All I/O operations are async (`async def`, `await`)
- Adapters yield data via `AsyncIterator` for memory-efficient streaming
- Services use batch processing (configurable `batch_size`, default 50)
- Every service/adapter has `connect()` and `disconnect()` methods
- Guard: `if not self.client: raise RuntimeError("Not connected. Call connect() first.")`

**Pydantic:**
- Data models extend `BaseModel` with `Field(...)` for required, `Field(default=X, description="...")` for optional
- Entity types live in `config/entity_types.py`, edge types in `config/edge_types.py`
- Environment config uses `pydantic_settings.BaseSettings` with `@lru_cache` singleton
- Export models in `__init__.py` via `__all__`

**Adapters:**
- `BaseAdapter` is the generic abstract class for all data sources (`connect`, `disconnect`, `fetch_items`, `get_conversation`)
- `BaseEmailAdapter(BaseAdapter)` adds email-specific methods (`fetch_emails`, `fetch_emails_by_domain`, `get_thread`, `search`)
- New adapters for non-email sources extend `BaseAdapter` directly
- Responsible ONLY for: connecting to provider, fetching raw data, normalizing to Pydantic models
- No business logic or graph operations in adapters
- Handle auth internally (OAuth2, API keys, etc.)

**Data Normalization:**
- All data from any source is normalized into a Pydantic model before ingestion
- Every model MUST implement `to_episode_content() -> str` (see `Email.to_episode_content()` as canonical example)
- Episode content is structured text with clear field labels, truncated to 10,000 chars max

**API:**
- FastAPI with lifespan context manager for startup/shutdown
- All endpoints return `{"success": bool, ...data}` shape
- Service unavailable (503) if GraphitiService not initialized
- API key auth via `X-API-Key` header (disabled when `CHAMP_GRAPH_API_KEY` not set)
- `/health` endpoint never requires auth
- Dual-mode ingest: `POST /api/ingest` accepts raw content or structured model bodies
- Bulk ingest: `POST /api/ingest/batch` up to 500 items
- Intelligence endpoints under `/api/accounts/{name}/intelligence/`

**Graph:**
- `group_id` = normalized account name (lowercase, hyphens only) via `_normalize_group_id()`
- Search uses `COMBINED_HYBRID_SEARCH_RRF` from graphiti-core
- Color scheme: Contact=#4ECDC4, Account=#FF6B6B, TeamMember=#45B7D1, Topic=#96CEB4, PersonalDetail=#FFEAA7, Communication=#DDA0DD, Opportunity=#FFB347, Branch=#FF69B4

**Branding:** When touching any file, update legacy references ("Email Knowledge Graph", "CEO WhatsApp Assistant") to "CHAMP Graph".

---

## How To: Add a New Data Source

1. **Create the model** in `models/` (e.g., `models/call_transcript.py`):
   - Extend `BaseModel`, include all metadata fields
   - Implement `to_episode_content() -> str` following `Email.to_episode_content()` format
   - Export in `models/__init__.py`

2. **Create the adapter** in `adapters/` (e.g., `adapters/zoom_adapter.py`):
   - Extend the base adapter class
   - Implement `connect()`, `disconnect()`, and data fetching methods
   - Normalize to the Pydantic model from step 1
   - Use `AsyncIterator` for streaming results

3. **Update graph schema** if the source introduces new entities or relationships:
   - Add Pydantic model to `config/entity_types.py`, update `ENTITY_TYPES` dict
   - Add edge model to `config/edge_types.py`, update `EDGE_TYPES` dict and `EDGE_TYPE_MAP`

4. **Wire into GraphitiService** — use the generic `ingest_episode()` or `ingest_episodes_bulk()` methods. These accept raw content strings + metadata and handle all graphiti-core interaction. No need to create source-specific ingestion methods.

5. **Create/extend sync service** with batch processing and incremental sync state tracking.

6. **Add API endpoints** if agents need direct access to the new data type.

---

## Status & Roadmap

### Implemented
- [x] Gmail adapter with OAuth2 (fetch by domain, date range, thread)
- [x] Outlook adapter with MS Graph API
- [x] Generic `BaseAdapter` abstract class + `BaseEmailAdapter` subclass
- [x] Generic `ingest_episode()` / `ingest_episodes_bulk()` — any data source can be ingested
- [x] Email convenience wrappers: `ingest_email()` / `ingest_emails_bulk()` (delegates to generic methods)
- [x] Normalized data models: Email, CallTranscript, TextMessage, SocialEngagement, MeetingNotes (all with `to_episode_content()`)
- [x] 8 entity types (Contact, Account, TeamMember, PersonalDetail, Topic, Communication, Opportunity, Branch)
- [x] 16 edge types including multi-modal (CALLED, TEXTED, MET_WITH, CONNECTED_ON, BELONGS_TO_BRANCH, COVERS_ACCOUNT, HAS_OPPORTUNITY, INVOLVED_IN)
- [x] EDGE_TYPE_MAP with 15 constraint entries
- [x] EmailSyncService: batch sync, incremental sync, priority sync, sync state tracking
- [x] FastAPI API: query, contacts, topics, communications, personal-details, team-contacts, graph endpoints
- [x] D3.js graph visualization (with colors for all 8 entity types)
- [x] Pydantic config with .env support
- [x] Setup verification tests

### Roadmap
- [x] Generalized `SyncService` with multi-adapter registry (alongside existing `EmailSyncService`)
- [x] Expose `POST /api/sync/{account_name}` endpoint
- [x] `POST /api/ingest` endpoint (raw text + structured dual-mode for agents to push data directly)
- [x] `POST /api/ingest/batch` bulk ingestion (up to 500 items)
- [x] Cross-salesperson discovery queries
- [x] Cross-branch relationship discovery (combined offers across divisions)
- [x] Contact timeline endpoint (all interactions across channels, chronologically)
- [x] Stakeholder mapping (champions, blockers, decision-makers)
- [x] Engagement gap detection (stale contacts)
- [x] Opportunity detection with stakeholder roles
- [x] API authentication (X-API-Key header)
- [x] Docker Compose for full stack (Neo4j + API server)
- [x] Railway deployment config
- [x] Comprehensive test suite (unit tests)
- [ ] Call transcript adapter (Gong, Zoom, Fireflies)
- [ ] SMS/text adapter (Twilio)
- [ ] Social engagement adapter (LinkedIn, Twitter/X — messages, likes, comments, connections)
- [ ] Meeting notes adapter (calendar events, summaries)
- [x] MCP Server with 9 tools (remember, recall, log_call, log_email, get_briefing, get_email_context, get_stakeholders, get_timeline, find_stale_contacts)
- [x] Agent hook endpoints (`/api/hooks/email`, `/api/hooks/email/batch`, `/api/hooks/call`) — simplified flat payloads
- [x] Email context endpoint (`/api/accounts/{name}/email-context`) — purpose-built for email composition agents
- [x] Briefing REST endpoint (`/api/accounts/{name}/briefing`)
- [x] GraffitiClient Python SDK (`sdk/`) — async HTTP client with retry, error handling, typed methods
- [ ] Webhook/push ingestion for real-time data
- [ ] Account auto-discovery from communication patterns
- [ ] Background enrichment pipeline (re-analyze existing graph for new connections)
- [ ] Multi-tenancy
- [ ] Integration tests (requires running Neo4j)
- [ ] `Competitor` entity type — track "We already use Vendor X" signals across transcripts
- [ ] `PainPoint` entity type — track objections, timing issues, budget concerns

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CHAMP_GRAPH_API_KEY` | No | — | API key for X-API-Key auth (disabled if unset) |
| `OPENAI_API_KEY` | Yes | — | OpenRouter API key |
| `OPENAI_BASE_URL` | Yes | `https://openrouter.ai/api/v1` | LLM endpoint |
| `MODEL_NAME` | Yes | `anthropic/claude-sonnet-4` | Model for entity extraction |
| `NEO4J_URI` | Yes | `bolt://localhost:7687` | Neo4j connection |
| `NEO4J_USER` | Yes | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | Yes | — | Neo4j password |
| `GOOGLE_CLIENT_ID` | For Gmail | — | Gmail OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | For Gmail | — | Gmail OAuth secret |
| `GOOGLE_REFRESH_TOKEN` | For Gmail | — | OAuth refresh token (from `setup_gmail_oauth.py`) |
| `GOOGLE_USER_EMAIL` | For Gmail | — | Authenticated Gmail address |
| `MS_CLIENT_ID` | For Outlook | — | Azure AD client ID |
| `MS_CLIENT_SECRET` | For Outlook | — | Azure AD secret |
| `MS_TENANT_ID` | For Outlook | — | Azure AD tenant ID |
| `MS_USER_EMAIL` | For Outlook | — | Outlook email address |
| `TEAM_DOMAINS` | Yes | — | Comma-separated internal domains (for direction detection) |
| `API_HOST` | No | `0.0.0.0` | API bind host |
| `API_PORT` | No | `8080` | API bind port |

---

## Agent Integration

CHAMP Graph exposes three integration layers for AI agents:

### Layer 1: MCP Server (Universal Agent Discovery)

Mounted at `/mcp` on the FastAPI server. Any MCP-compatible agent (ElevenLabs, Claude Desktop, LangChain) auto-discovers all tools.

**9 MCP Tools:**

| Tool | Type | Description |
|------|------|-------------|
| `remember` | Write | Store free-form information about an account |
| `log_call` | Write | Log a call with transcript and metadata |
| `log_email` | Write | Log an email interaction |
| `recall` | Read | Natural language search across account knowledge |
| `get_briefing` | Read | Comprehensive pre-interaction briefing |
| `get_email_context` | Read | Email composition context (history, personal details, topics) |
| `get_stakeholders` | Read | Stakeholder map + opportunities |
| `get_timeline` | Read | Cross-channel interaction timeline |
| `find_stale_contacts` | Read | Engagement gap detection |

**Claude Desktop config:**
```json
{
  "mcpServers": {
    "champ-graph": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

**ElevenLabs:** Agent Settings → Tools → Add Tool → MCP Server → enter URL.

**LangChain:**
```python
from langchain_mcp_adapters import MCPToolkit
toolkit = MCPToolkit(server_url="http://localhost:8080/mcp")
tools = toolkit.get_tools()
```

### Layer 2: REST API (Direct HTTP)

Full REST API at `/api/*` with X-API-Key auth. Use for server-to-server integration.

**Agent-friendly hook endpoints** (simplified flat payloads, no mode/data nesting):
- `POST /api/hooks/email` — Log a single email
- `POST /api/hooks/email/batch` — Log up to 100 emails
- `POST /api/hooks/call` — Log a call

**Context retrieval endpoints:**
- `GET /api/accounts/{name}/email-context?contact_name=X&contact_email=Y&subject=Z` — Email composition context
- `GET /api/accounts/{name}/briefing` — Pre-interaction briefing

### Layer 3: Python SDK (Import Directly)

For Python-based agent systems (like CHAMP Mail), import the SDK directly:

```python
from sdk import GraffitiClient

async with GraffitiClient(
    "https://your-champ-graph.railway.app",
    api_key="your-api-key",
) as graph:
    # Auto-ingest every sent/received email
    await graph.log_email(
        account_name="Acme Corp",
        from_address="rep@ourco.com",
        to_address="john@acme.com",
        subject="Follow-up on pricing",
        body="Hi John, ...",
        direction="outbound",
    )

    # Get context before composing a reply
    context = await graph.get_email_context(
        account_name="Acme Corp",
        contact_name="John Smith",
        subject="pricing",
    )
    # context.contacts, context.email_history, context.personal_details,
    # context.topics_discussed, context.stakeholders

    # Full briefing
    briefing = await graph.get_briefing("Acme Corp")

    # Natural language search
    result = await graph.recall("Acme Corp", "What pricing was discussed?")

    # Batch ingest
    await graph.log_email_batch("Acme Corp", [email1, email2, ...])
```

**SDK methods:** `log_email()`, `log_email_batch()`, `log_call()`, `remember()`, `get_email_context()`, `get_briefing()`, `recall()`, `get_timeline()`, `get_contacts()`, `get_stakeholders()`, `find_stale_contacts()`, `health_check()`

**Error handling:** Raises `GraffitiClientError` with `status_code` and `detail`. Auto-retries on 5xx and timeouts (configurable `max_retries`, default 2).

---

## Quick Commands

```bash
# Start Neo4j (Docker)
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password neo4j:5.26.2

# Run API server
python api_server.py

# Verify setup (Neo4j, Graphiti, config)
python test_setup.py

# Setup Gmail OAuth (one-time)
python setup_gmail_oauth.py

# Neo4j Browser
open http://localhost:7474

# Graph Visualization (after API is running)
open visualization/index.html

# Run tests (no Neo4j needed — everything mocked)
pytest tests/ -v

# Inspect MCP tool schemas (as agents see them)
fastmcp inspect mcp_server.py:mcp

# Interactive MCP inspector (browser-based)
fastmcp dev inspector mcp_server.py:mcp
```
