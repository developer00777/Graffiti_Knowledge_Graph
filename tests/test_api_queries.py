"""Tests for query, timeline, relationship, and intelligence API endpoints."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import api_server


@pytest.fixture
def client(mock_graphiti_service):
    """TestClient with auth disabled."""
    api_server.graphiti_service = mock_graphiti_service
    api_server._start_time = 1000.0

    with patch("api.auth.get_settings") as mock_settings:
        mock_settings.return_value.api_key = None
        yield TestClient(api_server.app)

    api_server.graphiti_service = None


class TestQueryEndpoint:
    def test_basic_query(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/query",
            json={"account": "Acme", "query": "Who are the contacts?"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        mock_graphiti_service.search_account.assert_called_once_with(
            account_name="Acme",
            query="Who are the contacts?",
            num_results=20,
        )

    def test_query_custom_num_results(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/query",
            json={"account": "Acme", "query": "test", "num_results": 5},
        )
        assert resp.status_code == 200
        call_kwargs = mock_graphiti_service.search_account.call_args[1]
        assert call_kwargs["num_results"] == 5

    def test_query_missing_fields_422(self, client):
        resp = client.post("/api/query", json={"account": "Acme"})
        assert resp.status_code == 422


class TestContactsEndpoint:
    def test_get_contacts(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/contacts")
        assert resp.status_code == 200
        assert "contacts" in resp.json()


class TestTopicsEndpoint:
    def test_get_topics(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/topics")
        assert resp.status_code == 200
        assert "topics" in resp.json()


class TestCommunicationsEndpoint:
    def test_get_communications(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/communications")
        assert resp.status_code == 200
        assert "communications" in resp.json()

    def test_get_communications_with_limit(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/communications?limit=5")
        assert resp.status_code == 200
        mock_graphiti_service.query_recent_communications.assert_called_once_with(
            account_name="Acme", limit=5
        )


class TestPersonalDetailsEndpoint:
    def test_get_personal_details(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/personal-details")
        assert resp.status_code == 200
        assert "personal_details" in resp.json()


class TestTeamContactsEndpoint:
    def test_get_team_contacts(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/team-contacts")
        assert resp.status_code == 200
        assert "team_contacts" in resp.json()


class TestGraphEndpoint:
    def test_get_graph(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/graph")
        assert resp.status_code == 200
        assert "graph" in resp.json()


class TestTimelineEndpoint:
    def test_get_timeline(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/timeline")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["account_name"] == "Acme"
        assert "timeline" in body
        assert "total" in body

    def test_timeline_with_limit(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/timeline?limit=10")
        assert resp.status_code == 200
        mock_graphiti_service.query_timeline.assert_called_once_with(
            account_name="Acme", limit=10
        )


class TestRelationshipsEndpoint:
    def test_get_relationships(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/relationships")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["account_name"] == "Acme"
        assert "relationships" in body
        assert "total" in body


class TestIntelligenceEndpoints:
    def test_salesperson_overlap(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/intelligence/salesperson-overlap")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["account_name"] == "Acme"
        assert "overlaps" in body
        mock_graphiti_service.query_cross_salesperson_overlap.assert_called_once()

    def test_stakeholder_map(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/intelligence/stakeholder-map")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "stakeholders" in body
        mock_graphiti_service.query_stakeholder_map.assert_called_once()

    def test_engagement_gaps(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/intelligence/engagement-gaps")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "gaps" in body
        assert body["days_threshold"] == 30

    def test_engagement_gaps_custom_days(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/intelligence/engagement-gaps?days=14")
        assert resp.status_code == 200
        assert resp.json()["days_threshold"] == 14
        mock_graphiti_service.query_engagement_gaps.assert_called_once_with(
            "Acme", days_threshold=14
        )

    def test_cross_branch(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/intelligence/cross-branch")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "branches" in body
        mock_graphiti_service.query_cross_branch_connections.assert_called_once()

    def test_opportunities(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/Acme/intelligence/opportunities")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "opportunities" in body
        mock_graphiti_service.query_combined_opportunities.assert_called_once()


class TestHealthEndpoint:
    def test_health_with_service(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["service"] == "champ-graph"
        assert body["version"] == "2.0.0"
        assert body["neo4j_connected"] is True
        assert body["uptime_seconds"] > 0

    def test_health_without_service(self):
        api_server.graphiti_service = None
        api_server._start_time = 1000.0

        with patch("api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = None
            client = TestClient(api_server.app)
            resp = client.get("/health")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "unhealthy"
            assert body["neo4j_connected"] is False


class TestSyncEndpoints:
    def test_sync_returns_501_when_not_configured(self, client):
        resp = client.post("/api/sync/Acme")
        assert resp.status_code == 501

    def test_sync_status_empty_when_not_configured(self, client):
        resp = client.get("/api/sync/status")
        assert resp.status_code == 200
        assert resp.json()["accounts"] == {}
