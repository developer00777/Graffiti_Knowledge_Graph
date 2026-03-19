# CHAMP Graph

**Centralized High-context Agent Memory Platform**

A plug-and-play temporal knowledge graph service that ingests multi-modal communication data (emails, calls, texts, meetings, social) and builds a unified, queryable knowledge graph. Designed as the memory layer for AI agent systems like [ChampMail](https://github.com/Champ-Deep/ChampMail).

## Architecture

```
Data Sources (Email, Calls, SMS, Social, Meetings)
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
  [FastAPI :8080]  ── REST API (X-API-Key auth)
        |
        v
  [External Agents / ChampMail / Visualization]
```

**Key properties:**
- **Standalone** — Runs as its own container with its own Neo4j instance
- **Plug-and-play** — Any system pushes data via `POST /api/ingest`, queries via `POST /api/query`
- **Multi-modal** — Emails, calls, texts, meetings, and social engagements in one graph
- **Self-enriching** — Graphiti's LLM extraction builds entities and relationships automatically

## Quick Start

### Docker Compose (recommended)

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/Graphiti-knowledge-graph.git
cd Graphiti-knowledge-graph

# Configure
cp .env.example .env
# Edit .env — at minimum set OPENAI_API_KEY and NEO4J_PASSWORD

# Launch
docker compose up --build
```

This starts Neo4j + CHAMP Graph API. Verify:

```bash
curl http://localhost:8080/health
# {"status":"healthy","service":"champ-graph","version":"2.0.0","neo4j_connected":true,...}
```

### Local Development

```bash
# Prerequisites: Python 3.10+, Docker (for Neo4j)

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start Neo4j
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password neo4j:5.26.2

cp .env.example .env
# Edit .env

python api_server.py
```

### Railway Deployment

1. Push this repo to GitHub
2. Create a new Railway project with two services:
   - **Neo4j** — Use the Railway Neo4j template
   - **CHAMP Graph** — Deploy from this repo (auto-detects `railway.toml`)
3. Set environment variables on the CHAMP Graph service:
   - `NEO4J_URI` — `bolt://your-neo4j-service:7687`
   - `NEO4J_PASSWORD` — Your Neo4j password
   - `OPENAI_API_KEY` — Your OpenRouter key
   - `CHAMP_GRAPH_API_KEY` — Generate a secure key for production

## API Reference

All endpoints (except `/health`) require `X-API-Key` header when `CHAMP_GRAPH_API_KEY` is set.

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check (no auth) |
| `POST` | `/api/ingest` | Ingest a single episode (raw or structured) |
| `POST` | `/api/ingest/batch` | Bulk ingest up to 500 episodes |
| `POST` | `/api/query` | Semantic search across the knowledge graph |

### Account Queries

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/accounts/{name}/contacts` | All contacts at account |
| `GET` | `/api/accounts/{name}/topics` | Discussion topics |
| `GET` | `/api/accounts/{name}/communications` | Recent communications |
| `GET` | `/api/accounts/{name}/personal-details` | Contact personal details |
| `GET` | `/api/accounts/{name}/team-contacts` | Team members who engaged |
| `GET` | `/api/accounts/{name}/graph` | Full graph data |
| `GET` | `/api/accounts/{name}/timeline` | Cross-channel timeline |
| `GET` | `/api/accounts/{name}/relationships` | Relationship map |

### Intelligence

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/accounts/{name}/intelligence/salesperson-overlap` | Contacts with multi-team engagement |
| `GET` | `/api/accounts/{name}/intelligence/stakeholder-map` | Champions, blockers, decision-makers |
| `GET` | `/api/accounts/{name}/intelligence/engagement-gaps` | Stale contacts (default 30 days) |
| `GET` | `/api/accounts/{name}/intelligence/cross-branch` | Cross-branch connections |
| `GET` | `/api/accounts/{name}/intelligence/opportunities` | Opportunities with stakeholder roles |

### Sync

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/sync/{account_name}` | Trigger adapter-based sync |
| `GET` | `/api/sync/status` | Sync state for all accounts |

### Example: Ingest a call transcript

```bash
curl -X POST http://localhost:8080/api/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "account_name": "Acme Corp",
    "mode": "raw",
    "content": "Call with John Smith (VP Sales) about Q1 renewal. He mentioned evaluating a competitor.",
    "name": "Call: John Smith Q1",
    "source_description": "call (outbound)"
  }'
```

### Example: Ingest a structured email

```bash
curl -X POST http://localhost:8080/api/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "account_name": "Acme Corp",
    "mode": "email",
    "data": {
      "message_id": "msg-123",
      "from_email": "sarah@ourco.com",
      "to_emails": ["john@acme.com"],
      "subject": "Follow up: Q1 renewal",
      "body_text": "Hi John, sending the pricing proposal as discussed.",
      "timestamp": "2026-03-15T16:00:00Z",
      "direction": "outbound"
    }
  }'
```

### Example: ChampMail integration (Python)

```python
import httpx

CHAMP_GRAPH_URL = "http://champ-graph:8080"
API_KEY = "your-champ-graph-key"
HEADERS = {"X-API-Key": API_KEY}

async def push_email(account: str, email_data: dict):
    async with httpx.AsyncClient() as client:
        return await client.post(
            f"{CHAMP_GRAPH_URL}/api/ingest",
            json={"account_name": account, "mode": "email", "data": email_data},
            headers=HEADERS,
        )

async def query_account(account: str, question: str):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{CHAMP_GRAPH_URL}/api/query",
            json={"account": account, "query": question},
            headers=HEADERS,
        )
        return resp.json()
```

## Ingest Modes

| Mode | Description | Required field |
|------|-------------|---------------|
| `raw` | Free-text content + metadata | `content` |
| `email` | Structured email body | `data` (Email schema) |
| `call` | Call transcript | `data` (CallTranscript schema) |
| `text_message` | SMS/text message | `data` (TextMessage schema) |
| `social` | LinkedIn, Twitter, etc. | `data` (SocialEngagement schema) |
| `meeting` | Meeting notes | `data` (MeetingNotes schema) |

## Project Structure

```
CHAMP-Graph/
├── api_server.py              # FastAPI server
├── api/                       # API layer
│   ├── auth.py                # X-API-Key middleware
│   ├── models.py              # Request/response Pydantic models
│   └── ingest_helpers.py      # IngestMode → episode resolution
├── adapters/                  # Data source adapters
│   ├── base_adapter.py        # BaseAdapter + BaseEmailAdapter
│   ├── gmail_adapter.py       # Gmail/Google Workspace
│   └── outlook_adapter.py     # Microsoft 365/Outlook
├── config/                    # Configuration & graph schema
│   ├── settings.py            # Pydantic BaseSettings
│   ├── entity_types.py        # 8 entity types
│   ├── edge_types.py          # 16 edge types + EDGE_TYPE_MAP
│   └── accounts.py            # Target account configs
├── models/                    # Normalized data models
│   ├── email.py               # Email
│   ├── call_transcript.py     # CallTranscript
│   ├── text_message.py        # TextMessage
│   ├── social_engagement.py   # SocialEngagement
│   └── meeting_notes.py       # MeetingNotes
├── services/                  # Business logic
│   ├── graphiti_service.py    # Graphiti Core wrapper
│   ├── sync_service.py        # Email sync orchestration
│   └── multi_sync_service.py  # Multi-source SyncService
├── tests/                     # Test suite
├── visualization/             # D3.js graph viewer
├── Dockerfile
├── docker-compose.yml
├── railway.toml
└── requirements.txt
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CHAMP_GRAPH_API_KEY` | No | — | API key for auth (disabled if unset) |
| `OPENAI_API_KEY` | Yes | — | OpenRouter API key |
| `OPENAI_BASE_URL` | No | `https://openrouter.ai/api/v1` | LLM endpoint |
| `MODEL_NAME` | No | `anthropic/claude-sonnet-4` | Model for extraction |
| `NEO4J_URI` | Yes | `bolt://localhost:7687` | Neo4j connection |
| `NEO4J_USER` | No | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | Yes | — | Neo4j password |
| `TEAM_DOMAINS` | Yes | — | Comma-separated internal email domains |
| `API_HOST` | No | `0.0.0.0` | API bind host |
| `API_PORT` | No | `8080` | API bind port |

## Testing

```bash
pytest tests/ -v
pytest tests/ -v --cov=. --cov-report=term-missing
```

## License

MIT
