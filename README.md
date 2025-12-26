# Graphiti Knowledge Graph

A temporal knowledge graph system for building AI-aware relationship maps from email communications. Designed to integrate with the CEO WhatsApp Assistant for intelligent account insights.

## Overview

This system ingests emails from Gmail/Outlook and builds a knowledge graph that tracks:
- **Contacts** - People at target accounts
- **Accounts** - Companies/MQAs being tracked
- **Team Members** - Internal sales/marketing team
- **Topics** - Discussion subjects
- **Personal Details** - Family, hobbies, interests
- **Communications** - Interaction events with temporal tracking

## Architecture

```
CEO WhatsApp Assistant
        |
        v
   [API Server] (:8080)
        |
        v
   [GraphitiService]
        |
        v
   [Neo4j Database]
```

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Docker (for Neo4j)
- Gmail OAuth credentials (for email ingestion)

### 2. Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/Graphiti-knowledge-graph.git
cd Graphiti-knowledge-graph

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your credentials
```

### 3. Start Neo4j

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.26.2
```

### 4. Configure Gmail OAuth

```bash
python setup_gmail_oauth.py
```

### 5. Run the API Server

```bash
python api_server.py
```

The API will be available at `http://localhost:8080`

## API Endpoints

### Query Account Knowledge

```http
POST /api/query
Content-Type: application/json

{
  "account": "acme-corp",
  "query": "Who from our team contacted this account?"
}
```

### Pre-built Queries

```http
GET /api/accounts/{account_name}/contacts
GET /api/accounts/{account_name}/topics
GET /api/accounts/{account_name}/communications
GET /api/accounts/{account_name}/personal-details
```

### Ingest Emails

```http
POST /api/sync/{account_name}
```

## WhatsApp Assistant Integration

The CEO WhatsApp Assistant should connect to this API to query account information.

### Example Integration (Python)

```python
import httpx

KNOWLEDGE_GRAPH_URL = "http://localhost:8080"

async def query_account(account: str, question: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{KNOWLEDGE_GRAPH_URL}/api/query",
            json={"account": account, "query": question}
        )
        return response.json()

# Usage
result = await query_account(
    "acme-corp",
    "What personal details do we know about the CEO?"
)
```

### Example Integration (Node.js)

```javascript
const axios = require('axios');

const KNOWLEDGE_GRAPH_URL = 'http://localhost:8080';

async function queryAccount(account, question) {
  const response = await axios.post(`${KNOWLEDGE_GRAPH_URL}/api/query`, {
    account,
    query: question,
  });
  return response.data;
}
```

## Project Structure

```
Graphiti-knowledge-graph/
├── adapters/              # Email provider adapters
│   ├── base_adapter.py    # Abstract base class
│   ├── gmail_adapter.py   # Gmail/Google Workspace
│   └── outlook_adapter.py # Microsoft 365
├── config/                # Configuration
│   ├── settings.py        # Environment settings
│   ├── entity_types.py    # Custom entity definitions
│   └── edge_types.py      # Relationship definitions
├── models/                # Data models
│   └── email.py           # Email data class
├── services/              # Business logic
│   ├── graphiti_service.py # Graphiti wrapper
│   └── sync_service.py    # Email sync orchestration
├── visualization/         # D3.js graph viewer
│   └── index.html
├── api_server.py          # FastAPI server (WhatsApp integration)
├── requirements.txt
├── .env.example
└── README.md
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenRouter API key | Yes |
| `OPENAI_BASE_URL` | API base URL | Yes |
| `MODEL_NAME` | LLM model to use | Yes |
| `NEO4J_URI` | Neo4j connection URI | Yes |
| `NEO4J_USER` | Neo4j username | Yes |
| `NEO4J_PASSWORD` | Neo4j password | Yes |
| `GOOGLE_CLIENT_ID` | Gmail OAuth client ID | For Gmail |
| `GOOGLE_CLIENT_SECRET` | Gmail OAuth secret | For Gmail |
| `TEAM_DOMAINS` | Your company domains | Yes |
| `API_HOST` | API server host | No (default: 0.0.0.0) |
| `API_PORT` | API server port | No (default: 8080) |

## Development

```bash
# Run tests
python test_setup.py

# Format code
black .

# Type check
mypy .
```

## License

MIT
