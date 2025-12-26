"""
Email sync orchestration service.

Coordinates syncing emails from providers to the knowledge graph.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from adapters.base_adapter import BaseEmailAdapter
from config.accounts import AccountConfig, TOP_ACCOUNTS
from models.email import Email
from services.graphiti_service import GraphitiService

logger = logging.getLogger(__name__)


class EmailSyncService:
    """
    Orchestrates email syncing for all configured accounts.

    Handles:
    - Syncing all accounts
    - Syncing individual accounts
    - Incremental sync (daily)
    - Full historical sync
    - Batch processing
    """

    def __init__(
        self,
        email_adapter: BaseEmailAdapter,
        graphiti_service: GraphitiService,
        accounts: List[AccountConfig] = None,
        batch_size: int = 50,
    ):
        """
        Initialize sync service.

        Parameters
        ----------
        email_adapter : BaseEmailAdapter
            Email provider adapter (Gmail or Outlook)
        graphiti_service : GraphitiService
            Graphiti service for knowledge graph operations
        accounts : list of AccountConfig, optional
            Accounts to sync (defaults to TOP_ACCOUNTS)
        batch_size : int
            Number of emails to process per batch
        """
        self.email_adapter = email_adapter
        self.graphiti_service = graphiti_service
        self.accounts = accounts or TOP_ACCOUNTS
        self.batch_size = batch_size
        self.sync_state: Dict[str, datetime] = {}  # Track last sync per account

    async def sync_all_accounts(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        full_sync: bool = False,
    ) -> Dict[str, Dict]:
        """
        Sync emails for all configured accounts.

        Parameters
        ----------
        since : datetime, optional
            Start date for sync
        until : datetime, optional
            End date for sync
        full_sync : bool
            If True, sync full history regardless of last sync

        Returns
        -------
        dict
            Results per account
        """
        results = {}

        for account in self.accounts:
            logger.info(f"Syncing account: {account.name} (priority {account.priority})")

            try:
                count = await self.sync_account(account, since, until, full_sync)
                results[account.name] = {
                    'status': 'success',
                    'emails_processed': count,
                    'domains': account.domains,
                }
            except Exception as e:
                logger.error(f"Error syncing {account.name}: {e}")
                results[account.name] = {
                    'status': 'error',
                    'error': str(e),
                }

        return results

    async def sync_account(
        self,
        account: AccountConfig,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        full_sync: bool = False,
    ) -> int:
        """
        Sync emails for a single account.

        Parameters
        ----------
        account : AccountConfig
            Account to sync
        since : datetime, optional
            Start date
        until : datetime, optional
            End date
        full_sync : bool
            If True, ignore last sync state

        Returns
        -------
        int
            Number of emails processed
        """
        # Determine sync start date
        if full_sync:
            sync_since = since or (datetime.now() - timedelta(days=365))
        else:
            sync_since = self.sync_state.get(account.name) or since or (datetime.now() - timedelta(days=30))

        sync_until = until

        logger.info(f"Syncing {account.name} from {sync_since} to {sync_until or 'now'}")

        emails_batch: List[Email] = []
        total_processed = 0

        # Fetch emails for each domain associated with this account
        for domain in account.domains:
            logger.info(f"Fetching emails for domain: {domain}")

            try:
                async for email in self.email_adapter.fetch_emails_by_domain(
                    domain=domain,
                    since=sync_since,
                    until=sync_until,
                ):
                    # Enrich email with account info
                    email.account_name = account.name
                    email.account_domain = domain

                    emails_batch.append(email)

                    # Process in batches
                    if len(emails_batch) >= self.batch_size:
                        await self.graphiti_service.ingest_emails_bulk(
                            emails_batch,
                            account_name=account.name
                        )
                        total_processed += len(emails_batch)
                        logger.info(f"Processed {total_processed} emails for {account.name}")
                        emails_batch = []

            except Exception as e:
                logger.error(f"Error fetching emails for domain {domain}: {e}")
                continue

        # Process remaining emails
        if emails_batch:
            await self.graphiti_service.ingest_emails_bulk(
                emails_batch,
                account_name=account.name
            )
            total_processed += len(emails_batch)

        # Update sync state
        self.sync_state[account.name] = datetime.now()

        logger.info(f"Completed sync for {account.name}: {total_processed} emails")
        return total_processed

    async def incremental_sync(self, hours: int = 24) -> Dict[str, Dict]:
        """
        Run incremental sync for recent emails.

        Parameters
        ----------
        hours : int
            Number of hours to look back (default 24)

        Returns
        -------
        dict
            Sync results per account
        """
        since = datetime.now() - timedelta(hours=hours)
        logger.info(f"Running incremental sync (last {hours} hours)")
        return await self.sync_all_accounts(since=since)

    async def sync_priority_accounts(
        self,
        max_priority: int = 1,
        since: Optional[datetime] = None,
    ) -> Dict[str, Dict]:
        """
        Sync only high-priority accounts.

        Parameters
        ----------
        max_priority : int
            Maximum priority level to sync (1 = highest)
        since : datetime, optional
            Start date

        Returns
        -------
        dict
            Sync results
        """
        priority_accounts = [a for a in self.accounts if a.priority <= max_priority]
        logger.info(f"Syncing {len(priority_accounts)} priority accounts")

        results = {}
        for account in priority_accounts:
            try:
                count = await self.sync_account(account, since=since)
                results[account.name] = {'status': 'success', 'emails_processed': count}
            except Exception as e:
                results[account.name] = {'status': 'error', 'error': str(e)}

        return results

    def get_sync_status(self) -> Dict[str, Optional[str]]:
        """Get last sync time for each account"""
        return {
            account.name: (
                self.sync_state[account.name].isoformat()
                if account.name in self.sync_state
                else None
            )
            for account in self.accounts
        }
