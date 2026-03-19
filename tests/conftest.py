"""
Shared test fixtures for CHAMP Graph test suite.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from services.graphiti_service import GraphitiService


@pytest.fixture
def mock_graphiti_service():
    """Mocked GraphitiService that doesn't require Neo4j."""
    service = AsyncMock(spec=GraphitiService)
    service.client = True  # Truthy so health check sees it as connected

    empty_results = {"nodes": [], "edges": [], "communities": []}
    service.search_account = AsyncMock(return_value=empty_results)
    service.ingest_episode = AsyncMock()
    service.ingest_episodes_bulk = AsyncMock()
    service.get_account_graph = AsyncMock(return_value={"nodes": [], "edges": []})
    service.query_recent_communications = AsyncMock(return_value=[])
    service.query_who_reached_out = AsyncMock(return_value=[])
    service.query_personal_details = AsyncMock(return_value=[])
    service.query_contact_relationships = AsyncMock(return_value=[])
    service.query_timeline = AsyncMock(return_value=[])
    service.query_relationship_map = AsyncMock(return_value=[])
    service.query_cross_salesperson_overlap = AsyncMock(return_value=[])
    service.query_stakeholder_map = AsyncMock(return_value=[])
    service.query_engagement_gaps = AsyncMock(return_value=[])
    service.query_cross_branch_connections = AsyncMock(return_value=[])
    service.query_combined_opportunities = AsyncMock(return_value=[])

    return service


@pytest.fixture
def api_key():
    return "test-api-key-12345"


@pytest.fixture
def api_key_header(api_key):
    return {"X-API-Key": api_key}


@pytest.fixture
def sample_timestamp():
    return datetime(2026, 3, 15, 14, 30, 0, tzinfo=timezone.utc)
