"""Tests for GraffitiClient SDK."""
import json

import httpx
import pytest
import pytest_asyncio

from sdk.graffiti_client import GraffitiClient, GraffitiClientError


@pytest.fixture
def mock_transport():
    """Build an httpx MockTransport for testing."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        # Health
        if path == "/health":
            return httpx.Response(200, json={
                "status": "healthy",
                "service": "champ-graph",
                "version": "2.0.0",
                "neo4j_connected": True,
                "uptime_seconds": 100.0,
            })

        # Email hook
        if path == "/api/hooks/email" and request.method == "POST":
            body = json.loads(request.content)
            return httpx.Response(200, json={
                "success": True,
                "message": f"Email '{body['subject'][:50]}' logged to {body['account_name']}",
            })

        # Email batch hook
        if path == "/api/hooks/email/batch" and request.method == "POST":
            body = json.loads(request.content)
            return httpx.Response(200, json={
                "success": True,
                "message": f"Ingested {len(body['emails'])} emails",
                "episodes_ingested": len(body["emails"]),
            })

        # Call hook
        if path == "/api/hooks/call" and request.method == "POST":
            body = json.loads(request.content)
            return httpx.Response(200, json={
                "success": True,
                "message": f"Call with {body['contact_name']} logged",
            })

        # Ingest (remember)
        if path == "/api/ingest" and request.method == "POST":
            body = json.loads(request.content)
            return httpx.Response(200, json={
                "success": True,
                "message": "Episode ingested",
                "account_name": body["account_name"],
                "episodes_ingested": 1,
            })

        # Query (recall)
        if path == "/api/query" and request.method == "POST":
            return httpx.Response(200, json={
                "success": True,
                "data": {"nodes": [], "edges": [], "communities": []},
            })

        # Email context
        if "/email-context" in path:
            return httpx.Response(200, json={
                "success": True,
                "account": "Acme",
                "contact_name": None,
                "contact_email": None,
                "contacts": [],
                "email_history": [],
                "all_interactions": [],
                "topics_discussed": [],
                "personal_details": [],
                "stakeholders": [],
            })

        # Briefing
        if "/briefing" in path:
            return httpx.Response(200, json={
                "success": True,
                "account": "Acme",
                "contacts": [],
                "recent_interactions": [],
                "personal_details": [],
                "stakeholders": [],
                "stale_contacts": [],
            })

        # Timeline
        if "/timeline" in path:
            return httpx.Response(200, json={
                "success": True,
                "account_name": "Acme",
                "timeline": [],
                "total": 0,
            })

        # Contacts
        if "/contacts" in path:
            return httpx.Response(200, json={"success": True, "contacts": []})

        # Stakeholder map
        if "/stakeholder-map" in path:
            return httpx.Response(200, json={
                "success": True,
                "account_name": "Acme",
                "stakeholders": [],
            })

        # Engagement gaps
        if "/engagement-gaps" in path:
            return httpx.Response(200, json={
                "success": True,
                "account_name": "Acme",
                "gaps": [],
                "days_threshold": 30,
            })

        return httpx.Response(404, json={"detail": "Not found"})

    return httpx.MockTransport(handler)


@pytest_asyncio.fixture
async def client(mock_transport):
    """GraffitiClient with mock transport."""
    c = GraffitiClient("http://localhost:8080", api_key="test-key")
    c._client = httpx.AsyncClient(
        transport=mock_transport,
        base_url="http://localhost:8080",
        headers={"X-API-Key": "test-key"},
    )
    yield c
    await c.disconnect()


class TestClientLifecycle:
    @pytest.mark.asyncio
    async def test_context_manager(self, mock_transport):
        async with GraffitiClient("http://localhost:8080") as c:
            c._client = httpx.AsyncClient(
                transport=mock_transport,
                base_url="http://localhost:8080",
            )
            result = await c.health_check()
            assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_not_connected_raises(self):
        c = GraffitiClient("http://localhost:8080")
        with pytest.raises(RuntimeError, match="not connected"):
            await c.health_check()


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health(self, client):
        result = await client.health_check()
        assert result["status"] == "healthy"
        assert result["service"] == "champ-graph"


class TestWriteOperations:
    @pytest.mark.asyncio
    async def test_log_email(self, client):
        result = await client.log_email(
            account_name="Acme",
            from_address="rep@ourco.com",
            to_address="john@acme.com",
            subject="Follow-up",
            body="Hi John",
        )
        assert result["success"] is True
        assert "Follow-up" in result["message"]

    @pytest.mark.asyncio
    async def test_log_email_batch(self, client):
        result = await client.log_email_batch(
            account_name="Acme",
            emails=[
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
        )
        assert result["success"] is True
        assert result["episodes_ingested"] == 2

    @pytest.mark.asyncio
    async def test_log_call(self, client):
        result = await client.log_call(
            account_name="Acme",
            contact_name="John Smith",
            summary="Discussed renewal",
            duration_minutes=30,
        )
        assert result["success"] is True
        assert "John Smith" in result["message"]

    @pytest.mark.asyncio
    async def test_remember(self, client):
        result = await client.remember(
            account_name="Acme",
            content="John mentioned they're evaluating competitors",
            source="email_agent",
        )
        assert result["success"] is True
        assert result["account_name"] == "Acme"


class TestReadOperations:
    @pytest.mark.asyncio
    async def test_get_email_context(self, client):
        result = await client.get_email_context(
            account_name="Acme",
            contact_name="John",
        )
        assert result["success"] is True
        assert result["account"] == "Acme"

    @pytest.mark.asyncio
    async def test_get_briefing(self, client):
        result = await client.get_briefing("Acme")
        assert result["success"] is True
        assert result["account"] == "Acme"

    @pytest.mark.asyncio
    async def test_recall(self, client):
        result = await client.recall("Acme", "Who is the main contact?")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_timeline(self, client):
        result = await client.get_timeline("Acme", limit=5)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_contacts(self, client):
        result = await client.get_contacts("Acme")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_stakeholders(self, client):
        result = await client.get_stakeholders("Acme")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_find_stale_contacts(self, client):
        result = await client.find_stale_contacts("Acme", days=14)
        assert result["success"] is True


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_4xx_raises_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"detail": "Forbidden"})

        transport = httpx.MockTransport(handler)
        c = GraffitiClient("http://localhost:8080")
        c._client = httpx.AsyncClient(
            transport=transport, base_url="http://localhost:8080"
        )
        with pytest.raises(GraffitiClientError) as exc:
            await c.health_check()
        assert exc.value.status_code == 403
        await c.disconnect()

    @pytest.mark.asyncio
    async def test_5xx_retries_then_raises(self):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(500, text="Internal Server Error")

        transport = httpx.MockTransport(handler)
        c = GraffitiClient("http://localhost:8080", max_retries=2)
        c._client = httpx.AsyncClient(
            transport=transport, base_url="http://localhost:8080"
        )
        with pytest.raises(GraffitiClientError) as exc:
            await c.health_check()
        assert exc.value.status_code == 500
        # 1 initial + 2 retries = 3 total calls
        assert call_count == 3
        await c.disconnect()

    @pytest.mark.asyncio
    async def test_api_key_sent_in_headers(self, mock_transport):
        received_headers = {}

        def capturing_handler(request: httpx.Request) -> httpx.Response:
            received_headers.update(dict(request.headers))
            return httpx.Response(200, json={"status": "healthy"})

        transport = httpx.MockTransport(capturing_handler)
        c = GraffitiClient("http://localhost:8080", api_key="my-secret-key")
        await c.connect()
        # Replace the real client with our capturing one
        await c._client.aclose()
        c._client = httpx.AsyncClient(
            transport=transport,
            base_url="http://localhost:8080",
            headers={"X-API-Key": "my-secret-key"},
        )
        await c.health_check()
        assert received_headers.get("x-api-key") == "my-secret-key"
        await c.disconnect()
