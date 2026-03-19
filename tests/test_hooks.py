"""Tests for webhook hook endpoints (/api/hooks/*)."""
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


class TestEmailHook:
    def test_logs_email(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/hooks/email",
            json={
                "account_name": "Acme",
                "from_address": "rep@ourco.com",
                "to_address": "john@acme.com",
                "subject": "Q2 Pricing Follow-up",
                "body": "Hi John, following up on our call...",
                "direction": "outbound",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "Q2 Pricing" in body["message"]
        mock_graphiti_service.ingest_episode.assert_called_once()
        kwargs = mock_graphiti_service.ingest_episode.call_args[1]
        assert "rep@ourco.com" in kwargs["content"]
        assert "john@acme.com" in kwargs["content"]
        assert "Q2 Pricing Follow-up" in kwargs["content"]
        assert kwargs["source_description"] == "email (outbound)"
        assert kwargs["account_name"] == "Acme"

    def test_logs_inbound_email(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/hooks/email",
            json={
                "account_name": "Acme",
                "from_address": "john@acme.com",
                "to_address": "rep@ourco.com",
                "subject": "Re: pricing",
                "body": "Sounds good",
                "direction": "inbound",
            },
        )
        assert resp.status_code == 200
        kwargs = mock_graphiti_service.ingest_episode.call_args[1]
        assert kwargs["source_description"] == "email (inbound)"

    def test_missing_required_field_422(self, client):
        resp = client.post(
            "/api/hooks/email",
            json={
                "account_name": "Acme",
                "from_address": "rep@ourco.com",
                # missing to_address, subject, body
            },
        )
        assert resp.status_code == 422

    def test_default_direction_outbound(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/hooks/email",
            json={
                "account_name": "Acme",
                "from_address": "rep@ourco.com",
                "to_address": "john@acme.com",
                "subject": "Hello",
                "body": "Test",
            },
        )
        assert resp.status_code == 200
        kwargs = mock_graphiti_service.ingest_episode.call_args[1]
        assert kwargs["source_description"] == "email (outbound)"

    def test_503_when_service_down(self):
        api_server.graphiti_service = None
        with patch("api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = None
            c = TestClient(api_server.app)
            resp = c.post(
                "/api/hooks/email",
                json={
                    "account_name": "Acme",
                    "from_address": "a@b.com",
                    "to_address": "c@d.com",
                    "subject": "test",
                    "body": "test",
                },
            )
            assert resp.status_code == 503


class TestEmailBatchHook:
    def test_batch_emails(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/hooks/email/batch",
            json={
                "account_name": "Acme",
                "emails": [
                    {
                        "account_name": "Acme",
                        "from_address": "rep@ourco.com",
                        "to_address": "john@acme.com",
                        "subject": "Email 1",
                        "body": "Body 1",
                    },
                    {
                        "account_name": "Acme",
                        "from_address": "john@acme.com",
                        "to_address": "rep@ourco.com",
                        "subject": "Email 2",
                        "body": "Body 2",
                        "direction": "inbound",
                    },
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["episodes_ingested"] == 2
        mock_graphiti_service.ingest_episodes_bulk.assert_called_once()

    def test_empty_batch_rejected(self, client):
        resp = client.post(
            "/api/hooks/email/batch",
            json={"account_name": "Acme", "emails": []},
        )
        assert resp.status_code == 422


class TestCallHook:
    def test_logs_call(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/hooks/call",
            json={
                "account_name": "Acme",
                "contact_name": "John Smith",
                "summary": "Discussed renewal pricing",
                "duration_minutes": 30,
                "direction": "outbound",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "John Smith" in body["message"]
        kwargs = mock_graphiti_service.ingest_episode.call_args[1]
        assert "John Smith" in kwargs["content"]
        assert "renewal pricing" in kwargs["content"]
        assert "30 minutes" in kwargs["content"]
        assert kwargs["source_description"] == "call (outbound)"

    def test_logs_call_with_transcript(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/hooks/call",
            json={
                "account_name": "Acme",
                "contact_name": "Jane",
                "summary": "Quick check-in",
                "transcript": "Jane: Hi! Rep: Hello, how's the project going?",
            },
        )
        assert resp.status_code == 200
        kwargs = mock_graphiti_service.ingest_episode.call_args[1]
        assert "how's the project going" in kwargs["content"]

    def test_default_direction_and_duration(self, client, mock_graphiti_service):
        resp = client.post(
            "/api/hooks/call",
            json={
                "account_name": "Acme",
                "contact_name": "Jane",
                "summary": "Test call",
            },
        )
        assert resp.status_code == 200
        kwargs = mock_graphiti_service.ingest_episode.call_args[1]
        assert kwargs["source_description"] == "call (outbound)"
        assert "0 minutes" in kwargs["content"]
