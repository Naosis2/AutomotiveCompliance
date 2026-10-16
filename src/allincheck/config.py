"""Application settings, loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Frozen settings object. Every threshold and timing lives here.

    Attributes:
        product_name: Name used in the User-Agent and reports.
        contact_email: Address sent in the User-Agent so dealers can reach us.
        request_delay_s: Minimum seconds between requests to one site.
        request_jitter_s: Extra random seconds added to the delay.
        request_timeout_s: Per-request timeout.
        max_retries: Retries on server errors.
        max_redirects: Redirect hops followed (each re-checked).
        max_listings_per_dealer: Cap on listing pages per dealer.
        max_response_bytes: Pages larger than this are skipped.
        site_wide_threshold: Same finding on this many listings becomes one site-wide finding.
    """

    model_config = SettingsConfigDict(
        env_prefix="ALLINCHECK_", env_file=".env", frozen=True, extra="ignore"
    )

    product_name: str = "AllInCheck"
    contact_email: str = Field(default="contact@example.com")
    request_delay_s: float = 2.0
    request_jitter_s: float = 1.0
    request_timeout_s: float = 20.0
    max_retries: int = 2
    max_redirects: int = 5
    max_listings_per_dealer: int = 50
    max_response_bytes: int = 3_000_000
    site_wide_threshold: int = 3

    @property
    def user_agent(self) -> str:
        """Return the User-Agent string including a contact address."""
        return f"{self.product_name}/0.1 (+mailto:{self.contact_email})"


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings object."""
    return Settings()
