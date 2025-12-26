"""
Account configuration for top MQAs (Marketing Qualified Accounts).

Define your target accounts here with their email domains.
The system will track all communications with these accounts.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class AccountConfig(BaseModel):
    """Configuration for a target account"""
    name: str = Field(..., description="Account/company name")
    domains: List[str] = Field(..., description="Email domains to track")
    aliases: Optional[List[str]] = Field(default=None, description="Alternative names")
    industry: Optional[str] = Field(default=None, description="Industry vertical")
    priority: int = Field(default=1, description="Priority level (1=highest)")
    notes: Optional[str] = Field(default=None, description="Additional notes")


# ============================================
# YOUR TOP 20-50 MQA ACCOUNTS
# ============================================
# Add your target accounts below. For each account:
# - name: The company name as you refer to it
# - domains: List of email domains (e.g., ["acme.com", "acme.io"])
# - industry: Optional industry classification
# - priority: 1-5 (1 being highest priority)
#
# Example:
# AccountConfig(
#     name="Acme Corporation",
#     domains=["acme.com", "acmecorp.com"],
#     industry="Technology",
#     priority=1
# ),
# ============================================

TOP_ACCOUNTS: List[AccountConfig] = [
    # === TIER 1 ACCOUNTS (Priority 1) ===
    AccountConfig(
        name="Example Corp",
        domains=["example.com"],
        industry="Technology",
        priority=1,
        notes="Key enterprise prospect"
    ),

    # === TIER 2 ACCOUNTS (Priority 2) ===
    AccountConfig(
        name="Sample Inc",
        domains=["sample.io", "sample.com"],
        industry="SaaS",
        priority=2
    ),

    # === ADD YOUR ACCOUNTS BELOW ===
    # AccountConfig(
    #     name="Company Name",
    #     domains=["company.com"],
    #     industry="Industry",
    #     priority=1
    # ),
]


def get_account_by_domain(domain: str) -> Optional[AccountConfig]:
    """Find account config by email domain"""
    domain = domain.lower()
    for account in TOP_ACCOUNTS:
        if domain in [d.lower() for d in account.domains]:
            return account
    return None


def get_account_by_name(name: str) -> Optional[AccountConfig]:
    """Find account config by name (case-insensitive)"""
    name_lower = name.lower()
    for account in TOP_ACCOUNTS:
        if account.name.lower() == name_lower:
            return account
        if account.aliases:
            if name_lower in [a.lower() for a in account.aliases]:
                return account
    return None
