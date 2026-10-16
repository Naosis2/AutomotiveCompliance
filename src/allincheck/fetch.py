"""Polite fetcher: robots.txt, spacing, retries, redirects checked, block detection."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from allincheck.config import Settings
from allincheck.urlguard import Resolver, UnsafeUrlError, check_public_url, system_resolver

log = logging.getLogger(__name__)

BLOCK_MARKERS = (
    "just a moment...",
    "cf-chl",
    "attention required",
    "captcha",
    "access denied",
    "request unsuccessful. incapsula",
    "px-captcha",
)


class FetchError(Exception):
    """Raised when a page cannot be fetched for a non-block reason."""


class BlockedError(FetchError):
    """Raised when the site blocks us or shows a bot challenge. Never bypassed."""


class RobotsDisallowedError(FetchError):
    """Raised when robots.txt does not allow the fetch."""


class PoliteFetcher:
    """Fetch pages one at a time per host, slowly, and stop at any block."""

    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        resolver: Resolver = system_resolver,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create a fetcher.

        Args:
            settings: Application settings.
            transport: Optional httpx transport (mock transport in tests).
            resolver: Hostname resolver used by the URL guard.
            sleep: Sleep function (replaced in tests).
            clock: Monotonic clock (replaced in tests).
        """
        self._s = settings
        self._resolver = resolver
        self._sleep = sleep
        self._clock = clock
        self._last: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._client = httpx.Client(
            transport=transport,
            timeout=settings.request_timeout_s,
            follow_redirects=False,
            headers={"User-Agent": settings.user_agent, "Accept": "text/html,application/xml"},
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def _wait(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            gap = self._s.request_delay_s + random.uniform(0, self._s.request_jitter_s)  # noqa: S311
            remaining = gap - (self._clock() - last)
            if remaining > 0:
                self._sleep(remaining)
        self._last[host] = self._clock()

    def _raw_get(self, url: str) -> httpx.Response:
        """GET with redirect hops each re-checked; no robots check."""
        current = url
        for _ in range(self._s.max_redirects + 1):
            try:
                check_public_url(current, self._resolver)
            except UnsafeUrlError as exc:
                raise FetchError(f"unsafe url: {exc}") from exc
            host = urlsplit(current).netloc
            resp: httpx.Response | None = None
            for attempt in range(self._s.max_retries + 1):
                self._wait(host)
                try:
                    resp = self._client.get(current)
                except httpx.TimeoutException as exc:
                    if attempt == self._s.max_retries:
                        raise FetchError("timeout") from exc
                    continue
                except httpx.HTTPError as exc:
                    raise FetchError(f"http error: {type(exc).__name__}") from exc
                if resp.status_code >= 500 and attempt < self._s.max_retries:
                    retry_after = resp.headers.get("Retry-After", "")
                    if retry_after.isdigit():
                        self._sleep(min(int(retry_after), 60))
                    continue
                break
            assert resp is not None  # noqa: S101
            if resp.is_redirect and "location" in resp.headers:
                current = urljoin(current, resp.headers["location"])
                continue
            return resp
        raise FetchError("too many redirects")

    def _robots_for(self, url: str) -> RobotFileParser | None:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser: RobotFileParser | None = None
            try:
                resp = self._raw_get(f"{origin}/robots.txt")
                if resp.status_code == 200:
                    parser = RobotFileParser()
                    parser.parse(resp.text.splitlines())
                elif resp.status_code in (401, 403):
                    raise BlockedError(f"robots.txt returned {resp.status_code}")
            except BlockedError:
                raise
            except FetchError:
                parser = None
            self._robots[origin] = parser
        return self._robots[origin]

    def get(self, url: str) -> str:
        """Fetch a page's text if robots.txt allows it and we are not blocked.

        Args:
            url: Public http/https URL.

        Returns:
            The response body text.

        Raises:
            RobotsDisallowedError: robots.txt disallows the URL for our User-Agent.
            BlockedError: The site returned a block or bot challenge.
            FetchError: Any other failure (timeout, bad status, too large).
        """
        robots = self._robots_for(url)
        if robots is not None and not robots.can_fetch(self._s.user_agent, url):
            raise RobotsDisallowedError(url)
        resp = self._raw_get(url)
        if resp.status_code in (401, 403, 429):
            raise BlockedError(f"status {resp.status_code}")
        if resp.status_code >= 400:
            raise FetchError(f"status {resp.status_code}")
        if len(resp.content) > self._s.max_response_bytes:
            raise FetchError("response too large")
        text = resp.text
        head = text[:4000].lower()
        if any(marker in head for marker in BLOCK_MARKERS):
            raise BlockedError("bot challenge detected")
        return text
