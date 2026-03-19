"""Tests for SyncService multi-source orchestration."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.base_adapter import BaseAdapter, BaseEmailAdapter
from config.accounts import AccountConfig
from services.multi_sync_service import SyncService, SyncTask


@pytest.fixture
def accounts():
    return [
        AccountConfig(
            name="Acme Corp",
            domains=["acme.com"],
            aliases=["Acme"],
        ),
    ]


@pytest.fixture
def sync_service(mock_graphiti_service, accounts):
    return SyncService(
        graphiti_service=mock_graphiti_service,
        accounts=accounts,
        batch_size=10,
    )


class TestSyncTask:
    def test_initial_state(self):
        task = SyncTask(account_name="Acme", source_type="email")
        assert task.status == "pending"
        assert task.items_processed == 0
        assert task.error is None
        assert task.task_id is not None

    def test_unique_task_ids(self):
        t1 = SyncTask(account_name="Acme", source_type="email")
        t2 = SyncTask(account_name="Acme", source_type="email")
        assert t1.task_id != t2.task_id


class TestAdapterRegistration:
    def test_register_generic_adapter(self, sync_service):
        adapter = MagicMock(spec=BaseAdapter)
        sync_service.register_adapter("call", adapter)
        assert "call" in sync_service.get_registered_sources()

    def test_register_email_adapter_creates_email_sync(self, sync_service):
        adapter = MagicMock(spec=BaseEmailAdapter)
        sync_service.register_adapter("email", adapter)
        assert sync_service._email_sync is not None
        assert "email" in sync_service.get_registered_sources()

    def test_register_multiple_adapters(self, sync_service):
        sync_service.register_adapter("call", MagicMock(spec=BaseAdapter))
        sync_service.register_adapter("sms", MagicMock(spec=BaseAdapter))
        sources = sync_service.get_registered_sources()
        assert "call" in sources
        assert "sms" in sources


class TestSyncAccount:
    @pytest.mark.asyncio
    async def test_email_sync_delegates(self, sync_service):
        email_adapter = MagicMock(spec=BaseEmailAdapter)
        sync_service.register_adapter("email", email_adapter)

        sync_service._email_sync.sync_account = AsyncMock(return_value=5)

        task = await sync_service.sync_account("Acme Corp", source_type="email")
        assert task.status == "completed"
        assert task.items_processed == 5

    @pytest.mark.asyncio
    async def test_missing_adapter_fails(self, sync_service):
        task = await sync_service.sync_account("Acme Corp", source_type="call")
        assert task.status == "failed"
        assert "No adapter registered" in task.error

    @pytest.mark.asyncio
    async def test_unknown_account_email_fails(self, sync_service):
        email_adapter = MagicMock(spec=BaseEmailAdapter)
        sync_service.register_adapter("email", email_adapter)
        sync_service._email_sync.sync_account = AsyncMock(return_value=0)

        task = await sync_service.sync_account("Unknown Corp", source_type="email")
        assert task.status == "failed"
        assert "Account not found" in task.error

    @pytest.mark.asyncio
    async def test_generic_sync_path(self, sync_service, mock_graphiti_service):
        adapter = MagicMock(spec=BaseAdapter)

        # Create mock items that the adapter will yield
        mock_item = MagicMock()
        mock_item.to_episode_content.return_value = "Call transcript content"
        mock_item.timestamp = datetime(2026, 3, 15, tzinfo=timezone.utc)
        mock_item.subject = None
        mock_item.title = None
        mock_item.content = "Call transcript content"

        async def mock_fetch(**kwargs):
            yield mock_item

        adapter.fetch_items = mock_fetch

        sync_service.register_adapter("call", adapter)
        task = await sync_service.sync_account("Acme Corp", source_type="call")
        assert task.status == "completed"
        assert task.items_processed == 1
        mock_graphiti_service.ingest_episodes_bulk.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_updates_state(self, sync_service, mock_graphiti_service):
        adapter = MagicMock(spec=BaseAdapter)

        async def mock_fetch(**kwargs):
            return
            yield  # Make it an async generator

        adapter.fetch_items = mock_fetch

        sync_service.register_adapter("call", adapter)
        await sync_service.sync_account("Acme Corp", source_type="call")
        status = sync_service.get_sync_status()
        assert "Acme Corp" in status
        assert "call" in status["Acme Corp"]
        assert status["Acme Corp"]["call"] is not None


class TestSyncStatus:
    def test_empty_status(self, sync_service):
        status = sync_service.get_sync_status()
        assert "Acme Corp" in status
        assert status["Acme Corp"] == {"email": None}

    @pytest.mark.asyncio
    async def test_status_after_sync(self, sync_service, mock_graphiti_service):
        adapter = MagicMock(spec=BaseAdapter)

        async def mock_fetch(**kwargs):
            return
            yield

        adapter.fetch_items = mock_fetch
        sync_service.register_adapter("call", adapter)
        await sync_service.sync_account("Acme Corp", source_type="call")

        status = sync_service.get_sync_status()
        assert status["Acme Corp"]["call"] is not None


class TestFindAccount:
    def test_find_by_exact_name(self, sync_service):
        account = sync_service._find_account("Acme Corp")
        assert account is not None
        assert account.name == "Acme Corp"

    def test_find_by_alias(self, sync_service):
        account = sync_service._find_account("Acme")
        assert account is not None
        assert account.name == "Acme Corp"

    def test_find_case_insensitive(self, sync_service):
        account = sync_service._find_account("acme corp")
        assert account is not None

    def test_find_nonexistent(self, sync_service):
        account = sync_service._find_account("Nonexistent")
        assert account is None


class TestBuildEpisodeName:
    def test_name_from_subject(self, sync_service):
        item = MagicMock()
        item.subject = "Pricing discussion"
        name = sync_service._build_episode_name(item, "email")
        assert name == "Email: Pricing discussion"

    def test_name_from_title(self, sync_service):
        item = MagicMock(spec=[])
        item.title = "Q1 Strategy Meeting"
        name = sync_service._build_episode_name(item, "meeting")
        assert name == "Meeting: Q1 Strategy Meeting"

    def test_name_fallback(self, sync_service):
        item = MagicMock(spec=[])
        name = sync_service._build_episode_name(item, "call")
        assert name == "Call episode"
