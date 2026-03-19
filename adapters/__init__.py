# Adapters module
from .base_adapter import BaseAdapter, BaseEmailAdapter
from .gmail_adapter import GmailAdapter
from .outlook_adapter import OutlookAdapter

__all__ = ['BaseAdapter', 'BaseEmailAdapter', 'GmailAdapter', 'OutlookAdapter']
