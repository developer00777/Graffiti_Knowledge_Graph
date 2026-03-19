"""Tests for MCP server tools."""
from datetime import datetime, timezone

import pytest

import api_server
from mcp_server import (
    find_stale_contacts,
    get_briefing,
    get_stakeholders,
    get_timeline,
    log_call,
    log_email,
    recall,
    remember,
)


@pytest.fixture
def service(mock_graphiti_service):
    """Inject mock service into api_server global."""
    api_server.graphiti_service = mock_graphiti_service
    yield mock_graphiti_service
    api_server.graphiti_service = None


class TestRemember:
    @pytest.mark.asyncio
    async def test_stores_episode(self, service):
        result = await remember(
            account_name="Acme Corp",
            content="Met with John, discussed Q2 pricing",
            source="voice_agent",
            name="Call with John",
        )
        assert result["success"] is True
        assert result["account_name"] == "Acme Corp"
        service.ingest_episode.assert_called_once()
        kwargs = service.ingest_episode.call_args[1]
        assert kwargs["account_name"] == "Acme Corp"
        assert "Q2 pricing" in kwargs["content"]
        assert "voice_agent" in kwargs["source_description"]

    @pytest.mark.asyncio
    async def test_default_source_and_name(self, service):
        result = await remember(account_name="Acme", content="Some note")
        assert result["success"] is True
        kwargs = service.ingest_episode.call_args[1]
        assert kwargs["name"] == "Agent note"
        assert "agent" in kwargs["source_description"]

    @pytest.mark.asyncio
    async def test_service_not_initialized(self):
        api_server.graphiti_service = None
        with pytest.raises(RuntimeError, match="not initialized"):
            await remember(account_name="X", content="test")


class TestRecall:
    @pytest.mark.asyncio
    async def test_searches_account(self, service):
        service.search_account.return_value = {
            "nodes": [{"name": "John", "labels": ["Contact"], "summary": "VP Sales"}],
            "edges": [{"fact": "John is the main contact", "name": "WORKS_AT"}],
            "communities": [],
        }
        result = await recall(account_name="Acme", query="Who is the main contact?")
        assert result["account"] == "Acme"
        assert len(result["facts"]) == 1
        assert "main contact" in result["facts"][0]
        assert result["entities"][0]["name"] == "John"
        assert result["entities"][0]["type"] == "Contact"

    @pytest.mark.asyncio
    async def test_empty_results(self, service):
        result = await recall(account_name="Acme", query="anything")
        assert result["account"] == "Acme"
        assert result["facts"] == []
        assert result["entities"] == []

    @pytest.mark.asyncio
    async def test_passes_num_results(self, service):
        await recall(account_name="Acme", query="test", num_results=5)
        service.search_account.assert_called_once_with("Acme", "test", 5)


class TestLogCall:
    @pytest.mark.asyncio
    async def test_logs_call(self, service):
        result = await log_call(
            account_name="Acme",
            contact_name="John Smith",
            summary="Discussed renewal pricing",
            duration_minutes=30,
            direction="outbound",
        )
        assert result["success"] is True
        assert "John Smith" in result["message"]
        kwargs = service.ingest_episode.call_args[1]
        assert "John Smith" in kwargs["content"]
        assert "renewal pricing" in kwargs["content"]
        assert "30 minutes" in kwargs["content"]
        assert kwargs["source_description"] == "call (outbound)"
        assert kwargs["account_name"] == "Acme"

    @pytest.mark.asyncio
    async def test_logs_call_with_transcript(self, service):
        result = await log_call(
            account_name="Acme",
            contact_name="Jane",
            summary="Quick check-in",
            transcript="Jane: Hi! Rep: Hello, how's the project going?",
        )
        assert result["success"] is True
        kwargs = service.ingest_episode.call_args[1]
        assert "how's the project going" in kwargs["content"]

    @pytest.mark.asyncio
    async def test_inbound_direction(self, service):
        await log_call(
            account_name="Acme",
            contact_name="Jane",
            summary="Inbound inquiry",
            direction="inbound",
        )
        kwargs = service.ingest_episode.call_args[1]
        assert kwargs["source_description"] == "call (inbound)"


class TestLogEmail:
    @pytest.mark.asyncio
    async def test_logs_email(self, service):
        result = await log_email(
            account_name="Acme",
            from_address="rep@ourco.com",
            to_address="john@acme.com",
            subject="Q2 Pricing Follow-up",
            body="Hi John, following up on our call...",
        )
        assert result["success"] is True
        assert "Q2 Pricing" in result["message"]
        kwargs = service.ingest_episode.call_args[1]
        assert "rep@ourco.com" in kwargs["content"]
        assert "john@acme.com" in kwargs["content"]
        assert "Q2 Pricing Follow-up" in kwargs["content"]
        assert kwargs["source_description"] == "email (outbound)"

    @pytest.mark.asyncio
    async def test_inbound_email(self, service):
        await log_email(
            account_name="Acme",
            from_address="john@acme.com",
            to_address="rep@ourco.com",
            subject="Re: pricing",
            body="Sounds good",
            direction="inbound",
        )
        kwargs = service.ingest_episode.call_args[1]
        assert kwargs["source_description"] == "email (inbound)"


class TestGetBriefing:
    @pytest.mark.asyncio
    async def test_assembles_briefing(self, service):
        service.search_account.return_value = {
            "nodes": [
                {"name": "John", "labels": ["Contact"], "summary": "VP Sales"},
                {"name": "Acme", "labels": ["Account"], "summary": "Target account"},
            ],
            "edges": [],
            "communities": [],
        }
        service.query_timeline.return_value = [
            {
                "timestamp": "2026-03-15",
                "channel": "email",
                "name": "Email: Pricing",
                "summary": "Sent pricing deck",
                "direction": "outbound",
            }
        ]
        service.query_personal_details.return_value = [
            {"fact": "John has two kids"}
        ]
        service.query_stakeholder_map.return_value = [
            {"person": "John", "relationship": "INVOLVED_IN", "target": "Renewal"}
        ]
        service.query_engagement_gaps.return_value = [
            {"contact_name": "Jane Smith"}
        ]

        result = await get_briefing(account_name="Acme")
        assert result["account"] == "Acme"
        # Only Contact nodes, not Account nodes
        assert len(result["contacts"]) == 1
        assert result["contacts"][0]["name"] == "John"
        assert len(result["recent_interactions"]) == 1
        assert "two kids" in result["personal_details"][0]
        assert len(result["stakeholders"]) == 1
        assert "Jane Smith" in result["stale_contacts"]

    @pytest.mark.asyncio
    async def test_empty_briefing(self, service):
        result = await get_briefing(account_name="NewAccount")
        assert result["account"] == "NewAccount"
        assert result["contacts"] == []
        assert result["recent_interactions"] == []
        assert result["personal_details"] == []
        assert result["stakeholders"] == []
        assert result["stale_contacts"] == []

    @pytest.mark.asyncio
    async def test_caps_recent_interactions_at_five(self, service):
        service.query_timeline.return_value = [
            {"timestamp": f"2026-03-{i}", "channel": "email", "name": f"Email {i}"}
            for i in range(10)
        ]
        result = await get_briefing(account_name="Acme")
        assert len(result["recent_interactions"]) == 5


class TestGetStakeholders:
    @pytest.mark.asyncio
    async def test_returns_stakeholders_and_opportunities(self, service):
        service.query_stakeholder_map.return_value = [
            {"person": "John", "relationship": "INVOLVED_IN", "target": "Deal"}
        ]
        service.query_combined_opportunities.return_value = [
            {"name": "Renewal", "involved": [{"person": "John", "role": "champion"}]}
        ]
        result = await get_stakeholders(account_name="Acme")
        assert result["account"] == "Acme"
        assert len(result["stakeholders"]) == 1
        assert result["stakeholders"][0]["person"] == "John"
        assert len(result["opportunities"]) == 1
        assert result["opportunities"][0]["name"] == "Renewal"

    @pytest.mark.asyncio
    async def test_empty_stakeholders(self, service):
        result = await get_stakeholders(account_name="Acme")
        assert result["stakeholders"] == []
        assert result["opportunities"] == []


class TestGetTimeline:
    @pytest.mark.asyncio
    async def test_returns_timeline(self, service):
        service.query_timeline.return_value = [
            {"timestamp": "2026-03-15", "channel": "call", "name": "Call: John"}
        ]
        result = await get_timeline(account_name="Acme", limit=10)
        assert result["account"] == "Acme"
        assert result["total"] == 1
        assert result["timeline"][0]["channel"] == "call"

    @pytest.mark.asyncio
    async def test_passes_limit(self, service):
        await get_timeline(account_name="Acme", limit=5)
        service.query_timeline.assert_called_once_with("Acme", limit=5)

    @pytest.mark.asyncio
    async def test_default_limit(self, service):
        await get_timeline(account_name="Acme")
        service.query_timeline.assert_called_once_with("Acme", limit=20)


class TestFindStaleContacts:
    @pytest.mark.asyncio
    async def test_returns_gaps(self, service):
        service.query_engagement_gaps.return_value = [
            {"contact_name": "Jane", "last_known_interaction": None}
        ]
        result = await find_stale_contacts(account_name="Acme", days=14)
        assert result["account"] == "Acme"
        assert result["days_threshold"] == 14
        assert result["total"] == 1
        assert result["stale_contacts"][0]["contact_name"] == "Jane"

    @pytest.mark.asyncio
    async def test_default_days(self, service):
        await find_stale_contacts(account_name="Acme")
        service.query_engagement_gaps.assert_called_once_with(
            "Acme", days_threshold=30
        )

    @pytest.mark.asyncio
    async def test_empty_gaps(self, service):
        result = await find_stale_contacts(account_name="Acme")
        assert result["total"] == 0
        assert result["stale_contacts"] == []
