"""
API Server for CEO WhatsApp Assistant Integration

Provides REST endpoints for querying the knowledge graph.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config.settings import get_settings
from services.graphiti_service import GraphitiService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global service instance
graphiti_service: Optional[GraphitiService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global graphiti_service
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
    logger.info("Knowledge graph service connected")

    yield

    await graphiti_service.disconnect()
    logger.info("Knowledge graph service disconnected")


app = FastAPI(
    title="Graphiti Knowledge Graph API",
    description="API for CEO WhatsApp Assistant to query account knowledge",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for external access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Request/Response Models ===

class QueryRequest(BaseModel):
    account: str
    query: str
    num_results: int = 20


class QueryResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    message: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str


# === Endpoints ===

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="graphiti-knowledge-graph"
    )


@app.post("/api/query", response_model=QueryResponse)
async def query_account(request: QueryRequest):
    """
    Query the knowledge graph for an account.

    This is the main endpoint for the CEO WhatsApp Assistant.
    """
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        results = await graphiti_service.search_account(
            account_name=request.account,
            query=request.query,
            num_results=request.num_results,
        )

        return QueryResponse(
            success=True,
            data=results,
        )
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/accounts/{account_name}/contacts")
async def get_account_contacts(account_name: str):
    """Get all contacts for an account"""
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    results = await graphiti_service.search_account(
        account_name=account_name,
        query="Who are the contacts and people at this account?",
    )
    return {"success": True, "contacts": results.get("nodes", [])}


@app.get("/api/accounts/{account_name}/topics")
async def get_account_topics(account_name: str):
    """Get all topics discussed with an account"""
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    results = await graphiti_service.search_account(
        account_name=account_name,
        query="What topics, subjects, and themes were discussed?",
    )
    return {"success": True, "topics": results.get("edges", [])}


@app.get("/api/accounts/{account_name}/communications")
async def get_account_communications(account_name: str, limit: int = 10):
    """Get recent communications with an account"""
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    results = await graphiti_service.query_recent_communications(
        account_name=account_name,
        limit=limit,
    )
    return {"success": True, "communications": results}


@app.get("/api/accounts/{account_name}/personal-details")
async def get_personal_details(account_name: str):
    """Get personal details about contacts at an account"""
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    results = await graphiti_service.query_personal_details(account_name)
    return {"success": True, "personal_details": results}


@app.get("/api/accounts/{account_name}/team-contacts")
async def get_team_contacts(account_name: str):
    """Get which team members contacted this account"""
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    results = await graphiti_service.query_who_reached_out(account_name)
    return {"success": True, "team_contacts": results}


@app.get("/api/accounts/{account_name}/graph")
async def get_account_graph(account_name: str):
    """Get full graph data for visualization"""
    if not graphiti_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    results = await graphiti_service.get_account_graph(account_name)
    return {"success": True, "graph": results}


# === Main ===

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
