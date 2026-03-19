"""
Base adapter interfaces for CHAMP Graph data source adapters.

BaseAdapter: Generic interface for any data source (calls, SMS, LinkedIn, etc.)
BaseEmailAdapter: Specialized interface for email providers (Gmail, Outlook, IMAP).
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import AsyncIterator, List, Optional

from pydantic import BaseModel

from models.email import Email


class BaseAdapter(ABC):
    """
    Abstract base class for all CHAMP Graph data source adapters.

    Any data source (email, calls, SMS, LinkedIn, meetings) must implement
    this interface. Implementations are responsible for:
    - Connecting/disconnecting from the data source
    - Fetching items as normalized Pydantic models
    - Retrieving conversation threads
    """

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to data source.

        This should handle authentication and initialization.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close connection to data source.

        Clean up any resources, close sessions, etc.
        """
        pass

    @abstractmethod
    async def fetch_items(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[BaseModel]:
        """
        Fetch items from the data source.

        Parameters
        ----------
        since : datetime, optional
            Only fetch items after this date
        until : datetime, optional
            Only fetch items before this date
        limit : int, optional
            Maximum number of items to fetch
        **kwargs
            Source-specific filter parameters

        Yields
        ------
        BaseModel
            Normalized data items (Email, CallTranscript, TextMessage, etc.)
        """
        pass

    @abstractmethod
    async def get_conversation(self, conversation_id: str) -> List[BaseModel]:
        """
        Get all items in a conversation thread.

        Parameters
        ----------
        conversation_id : str
            The thread/conversation ID

        Returns
        -------
        list of BaseModel
            All items in the conversation, ordered by date
        """
        pass


class BaseEmailAdapter(BaseAdapter):
    """
    Abstract base class for email provider adapters.

    Extends BaseAdapter with email-specific methods (domain filtering,
    email search, thread retrieval). Gmail and Outlook adapters extend this.
    """

    async def fetch_items(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[Email]:
        """Delegates to fetch_emails() for backward compatibility."""
        async for email in self.fetch_emails(
            since=since, until=until, limit=limit,
            from_addresses=kwargs.get('from_addresses'),
            to_addresses=kwargs.get('to_addresses'),
            labels=kwargs.get('labels'),
        ):
            yield email

    async def get_conversation(self, conversation_id: str) -> List[Email]:
        """Delegates to get_thread() for backward compatibility."""
        return await self.get_thread(conversation_id)

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
