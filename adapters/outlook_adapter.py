"""
Microsoft Outlook/365 adapter using Microsoft Graph API.

Requires Azure AD app registration with Mail.Read permissions.
"""
import logging
import re
from datetime import datetime
from html import unescape
from typing import AsyncIterator, Dict, List, Optional

import httpx

from adapters.base_adapter import BaseEmailAdapter
from models.email import Email, EmailDirection

logger = logging.getLogger(__name__)


class OutlookAdapter(BaseEmailAdapter):
    """
    Microsoft Graph API adapter for Outlook/Microsoft 365.

    Usage:
        adapter = OutlookAdapter(
            access_token="...",
            user_email="user@company.com",
            team_domains=["company.com"]
        )
        await adapter.connect()
        async for email in adapter.fetch_emails(since=datetime.now() - timedelta(days=30)):
            print(email.subject)
    """

    def __init__(
        self,
        access_token: str,
        user_email: str,
        team_domains: List[str],
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ):
        """
        Initialize Outlook adapter.

        Parameters
        ----------
        access_token : str
            OAuth2 access token for Microsoft Graph API
        user_email : str
            Email address of the authenticated user
        team_domains : list of str
            Your company's email domains (for direction detection)
        client_id, client_secret, tenant_id : str, optional
            Azure AD credentials for token refresh (if needed)
        """
        self.access_token = access_token
        self.user_email = user_email
        self.team_domains = [d.lower() for d in team_domains]
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id

        self.base_url = "https://graph.microsoft.com/v1.0"
        self.client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> None:
        """Create async HTTP client with auth headers"""
        logger.info(f"Connecting to Microsoft Graph as {self.user_email}")
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0
        )
        logger.info("Microsoft Graph connection established")

    async def disconnect(self) -> None:
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()
            self.client = None
        logger.info("Microsoft Graph connection closed")

    async def fetch_emails(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        from_addresses: Optional[List[str]] = None,
        to_addresses: Optional[List[str]] = None,
        labels: Optional[List[str]] = None,
        limit: Optional[int] = 100
    ) -> AsyncIterator[Email]:
        """Fetch emails from Outlook with filters"""
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")

        # Build OData filter
        filters = []
        if since:
            filters.append(f"receivedDateTime ge {since.isoformat()}Z")
        if until:
            filters.append(f"receivedDateTime lt {until.isoformat()}Z")

        params = {
            "$top": min(limit or 100, 1000),
            "$orderby": "receivedDateTime desc",
            "$select": "id,conversationId,subject,body,from,toRecipients,ccRecipients,receivedDateTime,hasAttachments,isRead,parentFolderId",
        }

        if filters:
            params["$filter"] = " and ".join(filters)

        logger.info(f"Fetching emails with params: {params}")

        fetched_count = 0
        next_link = f"{self.base_url}/me/messages"

        while next_link:
            try:
                if next_link == f"{self.base_url}/me/messages":
                    response = await self.client.get(next_link, params=params)
                else:
                    # @odata.nextLink includes params already
                    response = await self.client.get(next_link)

                response.raise_for_status()
                data = response.json()

                for msg in data.get('value', []):
                    if limit and fetched_count >= limit:
                        return

                    email = self._parse_outlook_message(msg)
                    if email:
                        # Apply from/to filters if specified
                        if from_addresses:
                            if email.from_email.lower() not in [a.lower() for a in from_addresses]:
                                continue
                        if to_addresses:
                            if not any(
                                t.lower() in [a.lower() for a in to_addresses]
                                for t in email.to_emails
                            ):
                                continue

                        fetched_count += 1
                        yield email

                # Get next page
                next_link = data.get('@odata.nextLink')

                if limit and fetched_count >= limit:
                    break

            except httpx.HTTPError as e:
                logger.error(f"HTTP error fetching emails: {e}")
                break

        logger.info(f"Fetched {fetched_count} emails from Outlook")

    async def fetch_emails_by_domain(
        self,
        domain: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: Optional[int] = 100
    ) -> AsyncIterator[Email]:
        """Fetch all emails involving a specific domain"""
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")

        domain = domain.lower()

        # Use $search for domain-based filtering
        # Note: $search doesn't work well with $filter, so we filter manually
        search_query = f"from:{domain} OR to:{domain}"

        params = {
            "$search": f'"{search_query}"',
            "$top": min(limit or 100, 1000),
            "$orderby": "receivedDateTime desc",
            "$select": "id,conversationId,subject,body,from,toRecipients,ccRecipients,receivedDateTime,hasAttachments",
        }

        logger.info(f"Fetching emails for domain {domain}")

        fetched_count = 0
        next_link = f"{self.base_url}/me/messages"

        while next_link:
            try:
                if next_link == f"{self.base_url}/me/messages":
                    response = await self.client.get(next_link, params=params)
                else:
                    response = await self.client.get(next_link)

                response.raise_for_status()
                data = response.json()

                for msg in data.get('value', []):
                    if limit and fetched_count >= limit:
                        return

                    email = self._parse_outlook_message(msg)
                    if email:
                        # Verify domain is in participants
                        participants = [email.from_email] + email.to_emails + (email.cc_emails or [])
                        if any(domain in p.lower() for p in participants):
                            # Apply date filters if specified
                            if since and email.timestamp < since:
                                continue
                            if until and email.timestamp > until:
                                continue

                            fetched_count += 1
                            yield email

                next_link = data.get('@odata.nextLink')

                if limit and fetched_count >= limit:
                    break

            except httpx.HTTPError as e:
                logger.error(f"HTTP error fetching emails: {e}")
                break

    async def get_thread(self, thread_id: str) -> List[Email]:
        """Get all emails in a conversation"""
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")

        # Microsoft Graph uses conversationId
        params = {
            "$filter": f"conversationId eq '{thread_id}'",
            "$orderby": "receivedDateTime asc",
            "$select": "id,conversationId,subject,body,from,toRecipients,ccRecipients,receivedDateTime,hasAttachments",
        }

        response = await self.client.get(
            f"{self.base_url}/me/messages",
            params=params
        )
        response.raise_for_status()
        data = response.json()

        emails = []
        for msg in data.get('value', []):
            email = self._parse_outlook_message(msg)
            if email:
                emails.append(email)

        return emails

    async def search(self, query: str, limit: Optional[int] = None) -> AsyncIterator[Email]:
        """Search emails using Microsoft Graph search"""
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")

        params = {
            "$search": f'"{query}"',
            "$top": min(limit or 100, 1000),
            "$select": "id,conversationId,subject,body,from,toRecipients,ccRecipients,receivedDateTime,hasAttachments",
        }

        response = await self.client.get(
            f"{self.base_url}/me/messages",
            params=params
        )
        response.raise_for_status()
        data = response.json()

        for msg in data.get('value', []):
            email = self._parse_outlook_message(msg)
            if email:
                yield email

    def _parse_outlook_message(self, msg: Dict) -> Optional[Email]:
        """Parse Microsoft Graph message to Email model"""
        try:
            # From
            from_data = msg.get('from', {}).get('emailAddress', {})
            from_email = from_data.get('address', '')
            from_name = from_data.get('name')

            # To recipients
            to_recipients = msg.get('toRecipients', [])
            to_emails = [r['emailAddress']['address'] for r in to_recipients if r.get('emailAddress')]
            to_names = [r['emailAddress'].get('name') for r in to_recipients if r.get('emailAddress')]

            # CC recipients
            cc_recipients = msg.get('ccRecipients', [])
            cc_emails = [r['emailAddress']['address'] for r in cc_recipients if r.get('emailAddress')]

            # Determine direction
            from_domain = from_email.split('@')[1].lower() if '@' in from_email else ''
            is_outbound = from_domain in self.team_domains
            direction = EmailDirection.OUTBOUND if is_outbound else EmailDirection.INBOUND

            # Body
            body_data = msg.get('body', {})
            body_content = body_data.get('content', '')
            body_type = body_data.get('contentType', 'text')

            if body_type.lower() == 'html':
                body_text = self._strip_html(body_content)
            else:
                body_text = body_content

            # Truncate if too long
            body_text = body_text[:10000] if len(body_text) > 10000 else body_text

            # Timestamp
            received_dt = msg.get('receivedDateTime', '')
            if received_dt:
                # Handle ISO format with Z suffix
                timestamp = datetime.fromisoformat(received_dt.replace('Z', '+00:00'))
            else:
                timestamp = datetime.now()

            # Subject
            subject = msg.get('subject', '(no subject)')
            is_reply = subject.lower().startswith('re:') or subject.lower().startswith('fwd:')

            return Email(
                message_id=msg['id'],
                thread_id=msg.get('conversationId'),
                from_email=from_email,
                from_name=from_name,
                to_emails=to_emails,
                to_names=to_names if any(to_names) else None,
                cc_emails=cc_emails if cc_emails else None,
                subject=subject,
                body_text=body_text,
                timestamp=timestamp,
                direction=direction,
                is_reply=is_reply,
                has_attachments=msg.get('hasAttachments', False),
                provider='outlook',
            )

        except Exception as e:
            logger.error(f"Error parsing Outlook message: {e}")
            return None

    def _strip_html(self, html: str) -> str:
        """Strip HTML tags and return plain text"""
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        html = re.sub(r'<[^>]+>', ' ', html)
        # Decode HTML entities
        html = unescape(html)
        # Clean up whitespace
        html = re.sub(r'\s+', ' ', html).strip()
        return html
