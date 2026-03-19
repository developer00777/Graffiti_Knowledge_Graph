"""Tests for ingest API endpoints."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import api_server


@pytest.fixture
def client(mock_graphiti_service):
    """TestClient with auth disabled for ingest tests."""
    api_server.graphiti_service = mock_graphiti_service
    api_server._start_time = 1000.0

    with patch("api.auth.get_settings") as mock_settings:
        mock_settings.return_value.api_key = None
        yield TestClient(api_server.app)

    api_server.graphiti_service = None


class TestSingleIngest:
    def test_raw_mode(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/ingest",
            json={
                "account_name": "Acme",
                "mode": "raw",
                "content": "Call with John about renewal",
                "name": "Call: John",
                "source_description": "call (outbound)",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["account_name"] == "Acme"
        assert body["episodes_ingested"] == 1
        mock_graphiti_service.ingest_episode.assert_called_once()

    def test_raw_mode_defaults(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/ingest",
            json={"account_name": "Acme", "mode": "raw", "content": "Some text"},
        )
        assert resp.status_code == 200
        call_kwargs = mock_graphiti_service.ingest_episode.call_args[1]
        assert call_kwargs["name"] == "Raw episode"
        assert call_kwargs["source_description"] == "Direct API ingestion"

    def test_raw_mode_missing_content_422(self, client):
        resp = client.post(
            "/api/ingest",
            json={"account_name": "Acme", "mode": "raw"},
        )
        assert resp.status_code == 422

    def test_email_structured_mode(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/ingest",
            json={
                "account_name": "Acme",
                "mode": "email",
                "data": {
                    "message_id": "msg-1",
                    "from_email": "sarah@ourco.com",
                    "to_emails": ["john@acme.com"],
                    "subject": "Follow up on renewal",
                    "body_text": "Hi John, here's the pricing.",
                    "timestamp": "2026-03-15T16:00:00Z",
                    "direction": "outbound",
                },
            },
        )
        assert resp.status_code == 200
        call_kwargs = mock_graphiti_service.ingest_episode.call_args[1]
        assert "Follow up on renewal" in call_kwargs["content"]
        assert "Email:" in call_kwargs["name"]

    def test_call_structured_mode(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/ingest",
            json={
                "account_name": "Acme",
                "mode": "call",
                "data": {
                    "call_id": "call-1",
                    "provider": "gong",
                    "caller": "Sarah",
                    "callee": "John",
                    "timestamp": "2026-03-15T14:00:00Z",
                    "transcript": "Let's talk about the deal.",
                    "direction": "outbound",
                },
            },
        )
        assert resp.status_code == 200
        call_kwargs = mock_graphiti_service.ingest_episode.call_args[1]
        assert "Call:" in call_kwargs["name"]

    def test_structured_missing_data_422(self, client):
        resp = client.post(
            "/api/ingest",
            json={"account_name": "Acme", "mode": "email"},
        )
        assert resp.status_code == 422

    def test_meeting_structured_mode(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/ingest",
            json={
                "account_name": "Acme",
                "mode": "meeting",
                "data": {
                    "meeting_id": "meet-1",
                    "provider": "google_calendar",
                    "title": "Q1 Review",
                    "organizer": "Sarah",
                    "attendees": ["John", "Jane"],
                    "start_time": "2026-03-15T14:00:00Z",
                    "notes": "Discussed targets.",
                },
            },
        )
        assert resp.status_code == 200
        call_kwargs = mock_graphiti_service.ingest_episode.call_args[1]
        assert "Meeting:" in call_kwargs["name"]


class TestBatchIngest:
    def test_batch_multiple_items(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/ingest/batch",
            json={
                "account_name": "Acme",
                "items": [
                    {"mode": "raw", "content": "Item 1"},
                    {"mode": "raw", "content": "Item 2"},
                    {"mode": "raw", "content": "Item 3"},
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["episodes_ingested"] == 3
        assert body["errors"] == []
        mock_graphiti_service.ingest_episodes_bulk.assert_called_once()

    def test_batch_with_mixed_modes(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/ingest/batch",
            json={
                "account_name": "Acme",
                "items": [
                    {"mode": "raw", "content": "Raw content"},
                    {
                        "mode": "email",
                        "data": {
                            "message_id": "msg-2",
                            "from_email": "sarah@ourco.com",
                            "to_emails": ["john@acme.com"],
                            "subject": "Test",
                            "body_text": "Hello",
                            "timestamp": "2026-03-15T16:00:00Z",
                            "direction": "outbound",
                        },
                    },
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["episodes_ingested"] == 2

    def test_batch_partial_errors(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/ingest/batch",
            json={
                "account_name": "Acme",
                "items": [
                    {"mode": "raw", "content": "Good item"},
                    {"mode": "email"},  # Missing data
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["episodes_ingested"] == 1
        assert len(body["errors"]) == 1
        assert "Item 1" in body["errors"][0]

    def test_batch_empty_items_rejected(self, client):
        resp = client.post(
            "/api/ingest/batch",
            json={"account_name": "Acme", "items": []},
        )
        assert resp.status_code == 422

    def test_batch_over_500_rejected(self, client):
        resp = client.post(
            "/api/ingest/batch",
            json={
                "account_name": "Acme",
                "items": [{"mode": "raw", "content": f"Item {i}"} for i in range(501)],
            },
        )
        assert resp.status_code == 422


class TestServiceDown:
    def test_ingest_503_when_service_not_initialized(self):
        """Test that 503 is returned when graphiti_service is None."""
        api_server.graphiti_service = None

        with patch("api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = None
            client = TestClient(api_server.app)
            resp = client.post(
                "/api/ingest",
                json={"account_name": "Acme", "mode": "raw", "content": "test"},
            )
            assert resp.status_code == 503
