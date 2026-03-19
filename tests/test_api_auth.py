"""Tests for API key authentication middleware."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import api_server


@pytest.fixture
def client_with_auth(mock_graphiti_service, api_key):
    """TestClient with API key auth enabled."""
    api_server.graphiti_service = mock_graphiti_service
    api_server._start_time = 1000.0

    with patch("api.auth.get_settings") as mock_settings:
        mock_settings.return_value.api_key = api_key
        yield TestClient(api_server.app)

    api_server.graphiti_service = None


@pytest.fixture
def client_no_auth(mock_graphiti_service):
    """TestClient with API key auth disabled (dev mode)."""
    api_server.graphiti_service = mock_graphiti_service
    api_server._start_time = 1000.0

    with patch("api.auth.get_settings") as mock_settings:
        mock_settings.return_value.api_key = None
        yield TestClient(api_server.app)

    api_server.graphiti_service = None


class TestAuthEnabled:
    def test_missing_api_key_returns_401(self, client_with_auth):
        resp = client_with_auth.post(
            "/api/query", json={"account": "Acme", "query": "test"}
        )
        assert resp.status_code == 401
        assert "missing_api_key" in resp.json()["detail"]["code"]

    def test_invalid_api_key_returns_403(self, client_with_auth):
        resp = client_with_auth.post(
            "/api/query",
            json={"account": "Acme", "query": "test"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 403
        assert "invalid_api_key" in resp.json()["detail"]["code"]

    def test_valid_api_key_allows_request(self, client_with_auth, api_key_header):
        resp = client_with_auth.post(
            "/api/query",
            json={"account": "Acme", "query": "test"},
            headers=api_key_header,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_health_does_not_require_auth(self, client_with_auth):
        resp = client_with_auth.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "champ-graph"

    def test_auth_required_on_ingest(self, client_with_auth):
        resp = client_with_auth.post(
            "/api/ingest",
            json={"account_name": "Acme", "mode": "raw", "content": "test"},
        )
        assert resp.status_code == 401

    def test_auth_required_on_batch(self, client_with_auth):
        resp = client_with_auth.post(
            "/api/ingest/batch",
            json={
                "account_name": "Acme",
                "items": [{"mode": "raw", "content": "test"}],
            },
        )
        assert resp.status_code == 401

    def test_auth_required_on_timeline(self, client_with_auth):
        resp = client_with_auth.get("/api/accounts/Acme/timeline")
        assert resp.status_code == 401

    def test_auth_required_on_intelligence(self, client_with_auth):
        resp = client_with_auth.get(
            "/api/accounts/Acme/intelligence/stakeholder-map"
        )
        assert resp.status_code == 401


class TestAuthDisabled:
    def test_no_key_needed_when_auth_disabled(self, client_no_auth):
        resp = client_no_auth.post(
            "/api/query", json={"account": "Acme", "query": "test"}
        )
        assert resp.status_code == 200

    def test_ingest_works_without_key(self, client_no_auth):
        resp = client_no_auth.post(
            "/api/ingest",
            json={"account_name": "Acme", "mode": "raw", "content": "test"},
        )
        assert resp.status_code == 200

    def test_health_works_without_key(self, client_no_auth):
        resp = client_no_auth.get("/health")
        assert resp.status_code == 200
