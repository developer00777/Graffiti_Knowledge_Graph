"""Tests for the get_email_context MCP tool."""
import pytest

import api_server
from mcp_server import get_email_context


@pytest.fixture
def service(mock_graphiti_service):
    """Inject mock service into api_server global."""
    api_server.graphiti_service = mock_graphiti_service
    yield mock_graphiti_service
    api_server.graphiti_service = None


class TestGetEmailContext:
    @pytest.mark.asyncio
    async def test_returns_full_context(self, service):
        service.search_account.return_value = {
            "nodes": [
                {"name": "John Smith", "labels": ["Contact"], "summary": "VP Sales at Acme"},
            ],
            "edges": [
                {"fact": "Discussed Q2 pricing", "name": "DISCUSSED_TOPIC"},
                {"fact": "John interested in volume discounts", "name": "INTERESTED_IN"},
            ],
            "communities": [],
        }
        service.query_timeline.return_value = [
            {
                "timestamp": "2026-03-15",
                "channel": "email",
                "name": "Email: Pricing deck",
                "summary": "Sent pricing deck to John Smith",
                "direction": "outbound",
            },
            {
                "timestamp": "2026-03-14",
                "channel": "call",
                "name": "Call: John Smith",
                "summary": "Discussed renewal with John Smith",
                "direction": "outbound",
            },
        ]
        service.query_personal_details.return_value = [
            {"fact": "John coaches little league"}
        ]
        service.query_stakeholder_map.return_value = [
            {"person": "John Smith", "relationship": "INVOLVED_IN", "target": "Renewal Deal"}
        ]

        result = await get_email_context(
            account_name="Acme",
            contact_name="John Smith",
            subject="pricing",
        )
        assert result["account"] == "Acme"
        assert result["contact_name"] == "John Smith"
        assert len(result["contacts"]) >= 1
        assert result["contacts"][0]["name"] == "John Smith"
        # Email history should only contain email channel
        assert len(result["email_history"]) == 1
        assert result["email_history"][0]["channel"] == "email"
        # All interactions includes calls
        assert len(result["all_interactions"]) == 2
        assert "Q2 pricing" in result["topics_discussed"][0]
        assert "little league" in result["personal_details"][0]
        assert result["stakeholders"][0]["person"] == "John Smith"

    @pytest.mark.asyncio
    async def test_filters_by_contact_email(self, service):
        service.search_account.return_value = {
            "nodes": [], "edges": [], "communities": [],
        }
        service.query_timeline.return_value = [
            {
                "timestamp": "2026-03-15",
                "channel": "email",
                "name": "Email: Test",
                "summary": "Email to john@acme.com about pricing",
            },
            {
                "timestamp": "2026-03-14",
                "channel": "email",
                "name": "Email: Other",
                "summary": "Email to jane@acme.com about renewal",
            },
        ]

        result = await get_email_context(
            account_name="Acme",
            contact_email="john@acme.com",
        )
        assert result["contact_email"] == "john@acme.com"
        assert len(result["email_history"]) == 1
        assert "john@acme.com" in result["email_history"][0]["summary"]

    @pytest.mark.asyncio
    async def test_no_filters_returns_all_emails(self, service):
        service.search_account.return_value = {
            "nodes": [], "edges": [], "communities": [],
        }
        service.query_timeline.return_value = [
            {"timestamp": "2026-03-15", "channel": "email", "name": "Email 1", "summary": "A"},
            {"timestamp": "2026-03-14", "channel": "email", "name": "Email 2", "summary": "B"},
            {"timestamp": "2026-03-13", "channel": "call", "name": "Call 1", "summary": "C"},
        ]

        result = await get_email_context(account_name="Acme")
        assert result["contact_name"] is None
        assert result["contact_email"] is None
        # Only email channel entries
        assert len(result["email_history"]) == 2
        # All interactions includes everything
        assert len(result["all_interactions"]) == 3

    @pytest.mark.asyncio
    async def test_empty_results(self, service):
        result = await get_email_context(account_name="Acme")
        assert result["account"] == "Acme"
        assert result["contacts"] == []
        assert result["email_history"] == []
        assert result["topics_discussed"] == []
        assert result["personal_details"] == []
        assert result["stakeholders"] == []

    @pytest.mark.asyncio
    async def test_service_not_initialized(self):
        api_server.graphiti_service = None
        with pytest.raises(RuntimeError, match="not initialized"):
            await get_email_context(account_name="Acme")

    @pytest.mark.asyncio
    async def test_caps_results(self, service):
        """Verify email_history is capped at 5 and stakeholders at 5."""
        service.search_account.return_value = {
            "nodes": [], "edges": [], "communities": [],
        }
        service.query_timeline.return_value = [
            {"timestamp": f"2026-03-{i}", "channel": "email", "name": f"Email {i}", "summary": f"email {i}"}
            for i in range(10)
        ]
        service.query_stakeholder_map.return_value = [
            {"person": f"Person {i}", "relationship": "INVOLVED_IN", "target": f"Deal {i}"}
            for i in range(10)
        ]

        result = await get_email_context(account_name="Acme")
        assert len(result["email_history"]) == 5
        assert len(result["stakeholders"]) == 5
