"""Find vehicle listing pages from sitemaps, then the inventory page."""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from allincheck.fetch import BlockedError, FetchError, PoliteFetcher

log = logging.getLogger(__name__)

LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)
VDP_RE = re.compile(
    r"/(?:vehicle|vehicles|vdp|inventory|used|new|detail|details|cars?)/[^?#]*\d", re.IGNORECASE
)
INVENTORY_PATHS = ("/inventory", "/used-inventory", "/new-inventory", "/vehicles", "/used")


def is_listing_url(url: str, site_host: str) -> bool:
    """Return True if a URL looks like a vehicle detail page on the dealer's own site.

    Args:
        url: Candidate URL.
        site_host: Dealer's hostname.

    Returns:
        Whether the URL looks like a listing page.
    """
    parts = urlsplit(url)
    if parts.hostname is None or parts.hostname.removeprefix("www.") != site_host.removeprefix(
        "www."
    ):
        return False
    return bool(VDP_RE.search(parts.path))


def _sitemap_urls(fetcher: PoliteFetcher, sitemap_url: str, depth: int = 0) -> list[str]:
    try:
        body = fetcher.get(sitemap_url)
    except FetchError as exc:
        if isinstance(exc, BlockedError):
            raise
        return []
    locs = LOC_RE.findall(body)
    if depth < 2 and "<sitemapindex" in body.lower():
        out: list[str] = []
        for child in locs[:10]:
            out.extend(_sitemap_urls(fetcher, child, depth + 1))
        return out
    return locs


def discover_listings(fetcher: PoliteFetcher, website_url: str, cap: int) -> list[str]:
    """Return up to `cap` listing URLs for a dealer.

    Args:
        fetcher: Polite fetcher.
        website_url: Dealer homepage URL.
        cap: Maximum number of listing URLs.

    Returns:
        Listing URLs, de-duplicated, in discovery order.

    Raises:
        BlockedError: The site blocked us; the caller marks the dealer blocked.
    """
    host = urlsplit(website_url).hostname or ""
    found: dict[str, None] = {}
    for loc in _sitemap_urls(fetcher, urljoin(website_url, "/sitemap.xml")):
        if is_listing_url(loc, host):
            found[loc] = None
        if len(found) >= cap:
            return list(found)
    if found:
        return list(found)
    pages = [website_url] + [urljoin(website_url, p) for p in INVENTORY_PATHS]
    for page in pages:
        try:
            html = fetcher.get(page)
        except BlockedError:
            raise
        except FetchError as exc:
            log.info("inventory page skipped", extra={"ctx": {"url": page, "why": str(exc)}})
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = str(a["href"])
            absolute = urljoin(page, href).split("#")[0]
            if is_listing_url(absolute, host):
                found[absolute] = None
            if len(found) >= cap:
                return list(found)
        if found:
            break
    return list(found)
