"""
Base types shared across all CHAMP Graph data models.
"""
from enum import Enum


class CommunicationDirection(str, Enum):
    """Direction of any communication (channel-agnostic)"""
    INBOUND = "inbound"    # They initiated contact with us
    OUTBOUND = "outbound"  # We initiated contact with them
