"""
Gmail API adapter for fetching emails from Google Workspace.

Requires Google OAuth2 credentials with Gmail API access.
"""
import base64
import logging
import re
from datetime import datetime
from typing import AsyncIterator, Dict, List, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource

from adapters.base_adapter import BaseEmailAdapter
from models.email import Email, EmailDirection

logger = logging.getLogger(__name__)


class GmailAdapter(BaseEmailAdapter):
    """
    Gmail API adapter for fetching and processing emails.

    Usage:
        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri='https://oauth2.googleapis.com/token'
        )
        adapter = GmailAdapter(credentials, "user@company.com", ["company.com"])
        await adapter.connect()
        async for email in adapter.fetch_emails(since=datetime.now() - timedelta(days=30)):
            print(email.subject)
    """

    def __init__(
        self,
        credentials: Credentials,
        user_email: str,
        team_domains: List[str]
    ):
        """
        Initialize Gmail adapter.

        Parameters
        ----------
        credentials : Credentials
            Google OAuth2 credentials
        user_email : str
            Email address of the authenticated user
        team_domains : list of str
            Your company's email domains (for direction detection)
        """
        self.credentials = credentials
        self.user_email = user_email
        self.team_domains = [d.lower() for d in team_domains]
        self.service: Optional[Resource] = None

    async def connect(self) -> None:
        """Build Gmail API service"""
        logger.info(f"Connecting to Gmail as {self.user_email}")
        self.service = build('gmail', 'v1', credentials=self.credentials)
        logger.info("Gmail connection established")

    async def disconnect(self) -> None:
        """Close Gmail service"""
        self.service = None
        logger.info("Gmail connection closed")

    async def fetch_emails(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        from_addresses: Optional[List[str]] = None,
        to_addresses: Optional[List[str]] = None,
        labels: Optional[List[str]] = None,
        limit: Optional[int] = 100
    ) -> AsyncIterator[Email]:
        """Fetch emails from Gmail with filters"""
        if not self.service:
            raise RuntimeError("Not connected. Call connect() first.")

        # Build Gmail search query
        query_parts = []

        if since:
            query_parts.append(f"after:{since.strftime('%Y/%m/%d')}")
        if until:
            query_parts.append(f"before:{until.strftime('%Y/%m/%d')}")
        if from_addresses:
            from_query = " OR ".join([f"from:{addr}" for addr in from_addresses])
            query_parts.append(f"({from_query})")
        if to_addresses:
            to_query = " OR ".join([f"to:{addr}" for addr in to_addresses])
            query_parts.append(f"({to_query})")

        query = " ".join(query_parts) if query_parts else None

        logger.info(f"Fetching emails with query: {query}")

        # Fetch message list
        request_params = {
            'userId': 'me',
            'maxResults': min(limit or 100, 500),
        }
        if query:
            request_params['q'] = query
        if labels:
            request_params['labelIds'] = labels

        page_token = None
        fetched_count = 0

        while True:
            if page_token:
                request_params['pageToken'] = page_token

            results = self.service.users().messages().list(**request_params).execute()
            messages = results.get('messages', [])

            for msg_ref in messages:
                if limit and fetched_count >= limit:
                    return

                try:
                    # Fetch full message
                    msg = self.service.users().messages().get(
                        userId='me',
                        id=msg_ref['id'],
                        format='full'
                    ).execute()

                    email = self._parse_gmail_message(msg)
                    if email:
                        fetched_count += 1
                        yield email

                except Exception as e:
                    logger.warning(f"Error fetching message {msg_ref['id']}: {e}")
                    continue

            # Check for more pages
            page_token = results.get('nextPageToken')
            if not page_token or (limit and fetched_count >= limit):
                break

        logger.info(f"Fetched {fetched_count} emails from Gmail")

    async def fetch_emails_by_domain(
        self,
        domain: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: Optional[int] = 100
    ) -> AsyncIterator[Email]:
        """Fetch all emails involving a specific domain"""
        domain = domain.lower()

        # Build query for emails to/from this domain
        query_parts = [f"(from:@{domain} OR to:@{domain})"]

        if since:
            query_parts.append(f"after:{since.strftime('%Y/%m/%d')}")
        if until:
            query_parts.append(f"before:{until.strftime('%Y/%m/%d')}")

        query = " ".join(query_parts)

        logger.info(f"Fetching emails for domain {domain}: {query}")

        # Use the generic fetch with our query
        request_params = {
            'userId': 'me',
            'q': query,
            'maxResults': min(limit or 100, 500),
        }

        page_token = None
        fetched_count = 0

        while True:
            if page_token:
                request_params['pageToken'] = page_token

            results = self.service.users().messages().list(**request_params).execute()
            messages = results.get('messages', [])

            for msg_ref in messages:
                if limit and fetched_count >= limit:
                    return

                try:
                    msg = self.service.users().messages().get(
                        userId='me',
                        id=msg_ref['id'],
                        format='full'
                    ).execute()

                    email = self._parse_gmail_message(msg)
                    if email:
                        # Double-check domain is in participants
                        participants = [email.from_email] + email.to_emails + (email.cc_emails or [])
                        if any(domain in p.lower() for p in participants):
                            fetched_count += 1
                            yield email

                except Exception as e:
                    logger.warning(f"Error fetching message {msg_ref['id']}: {e}")
                    continue

            page_token = results.get('nextPageToken')
            if not page_token or (limit and fetched_count >= limit):
                break

    async def get_thread(self, thread_id: str) -> List[Email]:
        """Get all emails in a conversation thread"""
        if not self.service:
            raise RuntimeError("Not connected. Call connect() first.")

        thread = self.service.users().threads().get(
            userId='me',
            id=thread_id,
            format='full'
        ).execute()

        emails = []
        for msg in thread.get('messages', []):
            email = self._parse_gmail_message(msg)
            if email:
                emails.append(email)

        # Sort by timestamp
        emails.sort(key=lambda e: e.timestamp)
        return emails

    async def search(self, query: str, limit: Optional[int] = None) -> AsyncIterator[Email]:
        """Search emails using Gmail search syntax"""
        if not self.service:
            raise RuntimeError("Not connected. Call connect() first.")

        request_params = {
            'userId': 'me',
            'q': query,
            'maxResults': min(limit or 100, 500),
        }

        results = self.service.users().messages().list(**request_params).execute()
        messages = results.get('messages', [])

        for msg_ref in messages:
            try:
                msg = self.service.users().messages().get(
                    userId='me',
                    id=msg_ref['id'],
                    format='full'
                ).execute()

                email = self._parse_gmail_message(msg)
                if email:
                    yield email

            except Exception as e:
                logger.warning(f"Error fetching message {msg_ref['id']}: {e}")
                continue

    def _parse_gmail_message(self, msg: Dict) -> Optional[Email]:
        """Parse Gmail API message to Email model"""
        try:
            headers = {
                h['name'].lower(): h['value']
                for h in msg.get('payload', {}).get('headers', [])
            }

            from_email = self._extract_email(headers.get('from', ''))
            from_name = self._extract_name(headers.get('from', ''))
            to_emails = self._extract_emails(headers.get('to', ''))
            to_names = [self._extract_name(t) for t in headers.get('to', '').split(',')]
            cc_emails = self._extract_emails(headers.get('cc', ''))

            # Determine direction based on team domains
            from_domain = from_email.split('@')[1].lower() if '@' in from_email else ''
            is_outbound = from_domain in self.team_domains
            direction = EmailDirection.OUTBOUND if is_outbound else EmailDirection.INBOUND

            # Get body text
            body = self._get_body_text(msg.get('payload', {}))

            # Check for attachments
            has_attachments = self._has_attachments(msg.get('payload', {}))

            # Parse timestamp
            timestamp = datetime.fromtimestamp(int(msg['internalDate']) / 1000)

            # Check if reply
            subject = headers.get('subject', '(no subject)')
            is_reply = subject.lower().startswith('re:') or subject.lower().startswith('fwd:')

            return Email(
                message_id=msg['id'],
                thread_id=msg.get('threadId'),
                from_email=from_email,
                from_name=from_name,
                to_emails=to_emails,
                to_names=to_names if any(to_names) else None,
                cc_emails=cc_emails if cc_emails else None,
                subject=subject,
                body_text=body,
                timestamp=timestamp,
                direction=direction,
                labels=msg.get('labelIds', []),
                is_reply=is_reply,
                has_attachments=has_attachments,
                provider='gmail',
            )

        except Exception as e:
            logger.error(f"Error parsing Gmail message: {e}")
            return None

    def _extract_email(self, header_value: str) -> str:
        """Extract email address from header like 'Name <email@domain.com>'"""
        match = re.search(r'<([^>]+)>', header_value)
        if match:
            return match.group(1).strip()
        # If no angle brackets, assume it's just the email
        return header_value.strip()

    def _extract_emails(self, header_value: str) -> List[str]:
        """Extract multiple email addresses from comma-separated header"""
        if not header_value:
            return []
        return [self._extract_email(part) for part in header_value.split(',') if part.strip()]

    def _extract_name(self, header_value: str) -> Optional[str]:
        """Extract display name from header like 'Name <email@domain.com>'"""
        match = re.match(r'^(.+?)\s*<', header_value)
        if match:
            name = match.group(1).strip().strip('"').strip("'")
            return name if name else None
        return None

    def _get_body_text(self, payload: Dict) -> str:
        """Extract plain text body from message payload"""
        # Direct text/plain body
        if payload.get('mimeType') == 'text/plain':
            data = payload.get('body', {}).get('data', '')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

        # Check parts for text/plain
        for part in payload.get('parts', []):
            if part.get('mimeType') == 'text/plain':
                data = part.get('body', {}).get('data', '')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

            # Nested multipart
            if part.get('mimeType', '').startswith('multipart/'):
                text = self._get_body_text(part)
                if text:
                    return text

        # Fallback: try to get HTML and strip tags
        html_body = self._get_html_body(payload)
        if html_body:
            return self._strip_html(html_body)

        return ""

    def _get_html_body(self, payload: Dict) -> str:
        """Extract HTML body from message payload"""
        if payload.get('mimeType') == 'text/html':
            data = payload.get('body', {}).get('data', '')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

        for part in payload.get('parts', []):
            if part.get('mimeType') == 'text/html':
                data = part.get('body', {}).get('data', '')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

        return ""

    def _strip_html(self, html: str) -> str:
        """Strip HTML tags and return plain text"""
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        html = re.sub(r'<[^>]+>', ' ', html)
        # Decode HTML entities
        from html import unescape
        html = unescape(html)
        # Clean up whitespace
        html = re.sub(r'\s+', ' ', html).strip()
        return html

    def _has_attachments(self, payload: Dict) -> bool:
        """Check if message has attachments"""
        for part in payload.get('parts', []):
            if part.get('filename'):
                return True
            if part.get('mimeType', '').startswith('multipart/'):
                if self._has_attachments(part):
                    return True
        return False
