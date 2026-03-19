"""
Multi-source sync orchestration service.

Provides a unified sync interface across all data source adapters.
Works alongside EmailSyncService (which handles email-specific logic).
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from adapters.base_adapter import BaseAdapter, BaseEmailAdapter
from config.accounts import AccountConfig, TOP_ACCOUNTS
from services.graphiti_service import GraphitiService
from services.sync_service import EmailSyncService

logger = logging.getLogger(__name__)


class SyncTask:
    """Tracks state of a sync operation."""

    def __init__(self, account_name: str, source_type: str):
        self.task_id: str = str(uuid.uuid4())
        self.account_name = account_name
        self.source_type = source_type
        self.status: str = "pending"
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.items_processed: int = 0
        self.error: Optional[str] = None


class SyncService:
    """
    Multi-source sync orchestrator.

    Maintains a registry of adapters keyed by source_type (e.g., "email", "call", "sms").
    Email adapters get delegated to EmailSyncService. Non-email adapters use the generic path.
    """

    def __init__(
        self,
        graphiti_service: GraphitiService,
        accounts: Optional[List[AccountConfig]] = None,
        batch_size: int = 50,
    ):
        self.graphiti_service = graphiti_service
        self.accounts = accounts or TOP_ACCOUNTS
        self.batch_size = batch_size

        self._adapters: Dict[str, BaseAdapter] = {}
        self._email_sync: Optional[EmailSyncService] = None

        # account -> {source_type -> last_sync}
        self.sync_state: Dict[str, Dict[str, datetime]] = {}
        self.active_tasks: Dict[str, SyncTask] = {}

    def register_adapter(self, source_type: str, adapter: BaseAdapter) -> None:
        """Register a data source adapter."""
        self._adapters[source_type] = adapter
        logger.info(f"Registered adapter for source type: {source_type}")

        if isinstance(adapter, BaseEmailAdapter):
            self._email_sync = EmailSyncService(
                email_adapter=adapter,
                graphiti_service=self.graphiti_service,
                accounts=self.accounts,
                batch_size=self.batch_size,
            )

    async def sync_account(
        self,
        account_name: str,
        source_type: str = "email",
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        full_sync: bool = False,
    ) -> SyncTask:
        """
        Sync data for an account from a specific source.

        Returns a SyncTask with status and items_processed count.
        """
        task = SyncTask(account_name=account_name, source_type=source_type)
        self.active_tasks[task.task_id] = task
        task.status = "running"
        task.started_at = datetime.now(timezone.utc)

        try:
            if source_type == "email" and self._email_sync:
                account_config = self._find_account(account_name)
                if not account_config:
                    raise ValueError(f"Account not found: {account_name}")
                count = await self._email_sync.sync_account(
                    account_config, since=since, until=until, full_sync=full_sync
                )
                task.items_processed = count
            else:
                adapter = self._adapters.get(source_type)
                if not adapter:
                    raise ValueError(f"No adapter registered for source type: {source_type}")

                count = await self._sync_generic(
                    adapter=adapter,
                    account_name=account_name,
                    source_type=source_type,
                    since=since,
                    until=until,
                    full_sync=full_sync,
                )
                task.items_processed = count

            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)

            if account_name not in self.sync_state:
                self.sync_state[account_name] = {}
            self.sync_state[account_name][source_type] = datetime.now(timezone.utc)

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc)
            logger.error(f"Sync failed for {account_name}/{source_type}: {e}")

        return task

    async def _sync_generic(
        self,
        adapter: BaseAdapter,
        account_name: str,
        source_type: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        full_sync: bool = False,
    ) -> int:
        """
        Generic sync path for non-email adapters.

        Fetches items via adapter.fetch_items(), calls to_episode_content(),
        and feeds into ingest_episodes_bulk().
        """
        last_sync = self.sync_state.get(account_name, {}).get(source_type)
        if full_sync:
            sync_since = since or (datetime.now(timezone.utc) - timedelta(days=365))
        else:
            sync_since = last_sync or since or (datetime.now(timezone.utc) - timedelta(days=30))

        batch: List[Dict[str, Any]] = []
        total_processed = 0

        async for item in adapter.fetch_items(since=sync_since, until=until):
            content = item.to_episode_content()

            ref_time = (
                getattr(item, "timestamp", None)
                or getattr(item, "start_time", None)
                or datetime.now(timezone.utc)
            )

            name = self._build_episode_name(item, source_type)

            batch.append(
                {
                    "name": name,
                    "content": content,
                    "reference_time": ref_time,
                    "source_description": f"{source_type} sync",
                }
            )

            if len(batch) >= self.batch_size:
                await self.graphiti_service.ingest_episodes_bulk(batch, account_name)
                total_processed += len(batch)
                logger.info(f"Processed {total_processed} items for {account_name}/{source_type}")
                batch = []

        if batch:
            await self.graphiti_service.ingest_episodes_bulk(batch, account_name)
            total_processed += len(batch)

        logger.info(f"Sync complete for {account_name}/{source_type}: {total_processed} items")
        return total_processed

    def _build_episode_name(self, item: BaseModel, source_type: str) -> str:
        """Build a human-readable episode name from a model instance."""
        if hasattr(item, "subject"):
            return f"Email: {item.subject[:50]}"
        if hasattr(item, "title") and item.title:
            return f"{source_type.capitalize()}: {item.title[:50]}"
        if hasattr(item, "body"):
            return f"{source_type.capitalize()}: {item.body[:50]}"
        if hasattr(item, "content") and item.content:
            return f"{source_type.capitalize()}: {item.content[:50]}"
        return f"{source_type.capitalize()} episode"

    def _find_account(self, account_name: str) -> Optional[AccountConfig]:
        """Find account config by name."""
        name_lower = account_name.lower()
        for account in self.accounts:
            if account.name.lower() == name_lower:
                return account
            if account.aliases and name_lower in [a.lower() for a in account.aliases]:
                return account
        return None

    def get_sync_status(self) -> Dict[str, Dict[str, Optional[str]]]:
        """Get last sync time for each account/source combination."""
        result: Dict[str, Dict[str, Optional[str]]] = {}
        for account in self.accounts:
            account_state = self.sync_state.get(account.name, {})
            result[account.name] = {
                source_type: ts.isoformat() if ts else None
                for source_type, ts in account_state.items()
            }
            if not result[account.name]:
                result[account.name] = {"email": None}
        return result

    def get_registered_sources(self) -> List[str]:
        """Get list of registered source types."""
        return list(self._adapters.keys())
