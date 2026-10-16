from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from allincheck.config import Settings
from allincheck.fetch import PoliteFetcher

FIX = Path(__file__).parent / "fixtures"


def public_resolver(host: str) -> list[str]:
    return ["93.184.216.34"]


@pytest.fixture
def settings() -> Settings:
    return Settings(request_delay_s=0, request_jitter_s=0, contact_email="t@example.com")


def make_fetcher(settings: Settings, handler: httpx.MockTransport) -> PoliteFetcher:
    return PoliteFetcher(
        settings, transport=handler, resolver=public_resolver, sleep=lambda s: None
    )
