"""Tests for email-context and briefing REST endpoints."""
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


class TestEmailContext:
    def test_returns_context(self, client, mock_graphiti_service):
        mock_graphiti_service.search_account.return_value = {
            "nodes": [{"name": "John", "labels": ["Contact"], "summary": "VP Sales"}],
            "edges": [{"fact": "Discussed pricing last week", "name": "DISCUSSED_TOPIC"}],
            "communities": [],
        }
        mock_graphiti_service.query_timeline.return_value = [
            {
                "timestamp": "2026-03-15",
                "channel": "email",
                "name": "Email: Pricing",
                "summary": "Sent pricing to John",
                "direction": "outbound",
            },
            {
                "timestamp": "2026-03-14",
                "channel": "call",
                "name": "Call: John",
                "summary": "Discussed renewal",
                "direction": "outbound",
            },
        ]
        mock_graphiti_service.query_personal_details.return_value = [
            {"fact": "John coaches little league"}
        ]
        mock_graphiti_service.query_stakeholder_map.return_value = [
            {"person": "John", "relationship": "INVOLVED_IN", "target": "Renewal"}
        ]

        resp = client.get(
            "/api/accounts/Acme/email-context",
            params={"contact_name": "John"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["account"] == "Acme"
        assert body["contact_name"] == "John"
        assert len(body["contacts"]) >= 1
        assert body["contacts"][0]["name"] == "John"
        assert len(body["email_history"]) >= 1
        assert body["email_history"][0]["channel"] == "email"
        assert "little league" in body["personal_details"][0]
        assert len(body["stakeholders"]) >= 1

    def test_returns_context_without_filters(self, client, mock_graphiti_service):
        mock_graphiti_service.query_timeline.return_value = [
            {"timestamp": "2026-03-15", "channel": "email", "name": "Email: Test", "summary": "Test"},
        ]
        resp = client.get("/api/accounts/Acme/email-context")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["contact_name"] is None
        assert body["contact_email"] is None

    def test_filters_email_history_by_contact(self, client, mock_graphiti_service):
        mock_graphiti_service.query_timeline.return_value = [
            {"timestamp": "2026-03-15", "channel": "email", "name": "Email: To John", "summary": "Pricing for john"},
            {"timestamp": "2026-03-14", "channel": "email", "name": "Email: To Jane", "summary": "Pricing for jane"},
        ]
        resp = client.get(
            "/api/accounts/Acme/email-context",
            params={"contact_name": "John"},
        )
        body = resp.json()
        # Only John's emails should appear
        assert len(body["email_history"]) == 1
        assert "john" in body["email_history"][0]["summary"].lower()

    def test_503_when_service_down(self):
        api_server.graphiti_service = None
        with patch("api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = None
            c = TestClient(api_server.app)
            resp = c.get("/api/accounts/Acme/email-context")
            assert resp.status_code == 503


class TestBriefingEndpoint:
    def test_returns_briefing(self, client, mock_graphiti_service):
        mock_graphiti_service.search_account.return_value = {
            "nodes": [
                {"name": "John", "labels": ["Contact"], "summary": "VP Sales"},
                {"name": "Acme", "labels": ["Account"], "summary": "Target account"},
            ],
            "edges": [],
            "communities": [],
        }
        mock_graphiti_service.query_timeline.return_value = [
            {"timestamp": "2026-03-15", "channel": "email", "name": "Email: Pricing"}
        ]
        mock_graphiti_service.query_personal_details.return_value = [
            {"fact": "John has two kids"}
        ]
        mock_graphiti_service.query_stakeholder_map.return_value = [
            {"person": "John", "relationship": "INVOLVED_IN", "target": "Renewal"}
        ]
        mock_graphiti_service.query_engagement_gaps.return_value = [
            {"contact_name": "Jane Smith"}
        ]

        resp = client.get("/api/accounts/Acme/briefing")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["account"] == "Acme"
        # Only Contact nodes, not Account nodes
        assert len(body["contacts"]) == 1
        assert body["contacts"][0]["name"] == "John"
        assert len(body["recent_interactions"]) == 1
        assert "two kids" in body["personal_details"][0]
        assert len(body["stakeholders"]) == 1
        assert "Jane Smith" in body["stale_contacts"]

    def test_empty_briefing(self, client, mock_graphiti_service):
        resp = client.get("/api/accounts/NewAccount/briefing")
        assert resp.status_code == 200
        body = resp.json()
        assert body["account"] == "NewAccount"
        assert body["contacts"] == []
        assert body["recent_interactions"] == []
        assert body["personal_details"] == []
        assert body["stakeholders"] == []
        assert body["stale_contacts"] == []
