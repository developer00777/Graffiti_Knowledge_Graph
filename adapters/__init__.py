# Adapters module
from .base_adapter import BaseEmailAdapter
from .gmail_adapter import GmailAdapter
from .outlook_adapter import OutlookAdapter

__all__ = ['BaseEmailAdapter', 'GmailAdapter', 'OutlookAdapter']
