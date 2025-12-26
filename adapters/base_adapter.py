"""
Base adapter interface for email providers.

All email provider adapters (Gmail, Outlook, IMAP) must implement this interface.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import AsyncIterator, List, Optional

from models.email import Email


class BaseEmailAdapter(ABC):
    """
    Abstract base class for email provider adapters.

    Implementations must provide methods to:
    - Connect/disconnect from the email service
    - Fetch emails with various filters
    - Fetch emails by domain (for account-based filtering)
    - Get email threads
    """

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to email provider.

        This should handle authentication and initialization.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close connection to email provider.

        Clean up any resources, close sessions, etc.
        """
        pass

    @abstractmethod
    async def fetch_emails(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        from_addresses: Optional[List[str]] = None,
        to_addresses: Optional[List[str]] = None,
        labels: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> AsyncIterator[Email]:
        """
        Fetch emails matching the given criteria.

        Parameters
        ----------
        since : datetime, optional
            Only fetch emails after this date
        until : datetime, optional
            Only fetch emails before this date
        from_addresses : list of str, optional
            Filter by sender addresses
        to_addresses : list of str, optional
            Filter by recipient addresses
        labels : list of str, optional
            Filter by labels/folders
        limit : int, optional
            Maximum number of emails to fetch

        Yields
        ------
        Email
            Normalized email objects
        """
        pass

    @abstractmethod
    async def fetch_emails_by_domain(
        self,
        domain: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> AsyncIterator[Email]:
        """
        Fetch all emails involving a specific domain.

        This is useful for account-based filtering - fetch all
        communications with a specific company.

        Parameters
        ----------
        domain : str
            Email domain to filter by (e.g., "acme.com")
        since : datetime, optional
            Only fetch emails after this date
        until : datetime, optional
            Only fetch emails before this date
        limit : int, optional
            Maximum number of emails to fetch

        Yields
        ------
        Email
            Normalized email objects involving the domain
        """
        pass

    @abstractmethod
    async def get_thread(self, thread_id: str) -> List[Email]:
        """
        Get all emails in a conversation thread.

        Parameters
        ----------
        thread_id : str
            The thread/conversation ID

        Returns
        -------
        list of Email
            All emails in the thread, ordered by date
        """
        pass

    @abstractmethod
    async def search(self, query: str, limit: Optional[int] = None) -> AsyncIterator[Email]:
        """
        Search emails using provider-native search.

        Parameters
        ----------
        query : str
            Search query (provider-specific syntax)
        limit : int, optional
            Maximum number of results

        Yields
        ------
        Email
            Matching email objects
        """
        pass
