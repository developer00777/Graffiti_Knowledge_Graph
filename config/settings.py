"""
Environment configuration settings
"""
import os
from functools import lru_cache
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # OpenRouter/OpenAI Configuration
    openai_api_key: str = Field(default="")
    openai_base_url: Optional[str] = Field(default="https://openrouter.ai/api/v1")
    model_name: str = Field(default="anthropic/claude-sonnet-4")

    # Neo4j Configuration
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="password")

    # Google Workspace Configuration
    google_client_id: Optional[str] = Field(default=None)
    google_client_secret: Optional[str] = Field(default=None)
    google_refresh_token: Optional[str] = Field(default=None)
    google_user_email: Optional[str] = Field(default=None)

    # Microsoft 365 Configuration
    ms_client_id: Optional[str] = Field(default=None)
    ms_client_secret: Optional[str] = Field(default=None)
    ms_tenant_id: Optional[str] = Field(default=None)
    ms_user_email: Optional[str] = Field(default=None)

    # API Authentication
    api_key: Optional[str] = Field(default=None, description="API key for X-API-Key header auth. If unset, auth is disabled.")

    # Team Configuration
    team_domains: str = Field(default="yourcompany.com")

    @property
    def team_domain_list(self) -> List[str]:
        """Parse team domains from comma-separated string"""
        return [d.strip() for d in self.team_domains.split(',') if d.strip()]

    @property
    def has_gmail_config(self) -> bool:
        """Check if Gmail configuration is complete"""
        return all([
            self.google_client_id,
            self.google_client_secret,
            self.google_refresh_token
        ])

    @property
    def has_outlook_config(self) -> bool:
        """Check if Outlook configuration is complete"""
        return all([
            self.ms_client_id,
            self.ms_client_secret,
            self.ms_tenant_id
        ])

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
