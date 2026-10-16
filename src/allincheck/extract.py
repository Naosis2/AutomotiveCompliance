"""Extract price, label, VIN and disclaimer text from a listing page."""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

from allincheck.models import Listing

PRICE_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d{4,7})(?:\.(\d{2}))?")
VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
DISCLAIMER_RE = re.compile(
    r"[^.\n]{0,120}\b(?:plus|taxes|fees|hst|licen[cs]ing|as-is|certification)\b[^.\n]{0,160}",
    re.IGNORECASE,
)
PLATFORM_FINGERPRINTS: dict[str, tuple[str, ...]] = {
    # Unconfirmed guesses; replace with fingerprints from saved Phase 0 pages (S5).
    "edealer": ("edealer",),
    "d2c_media": ("d2cmedia",),
    "sm360": ("sm360",),
    "carpages": ("carpages",),
    "dealer_eprocess": ("dealereprocess",),
}
MAX_TEXT = 20_000


def detect_platform(html: str) -> str:
    """Return the platform name matching known HTML fingerprints, else 'generic'.

    Args:
        html: Raw page HTML.

    Returns:
        Platform key.
    """
    low = html.lower()
    for name, needles in PLATFORM_FINGERPRINTS.items():
        if any(n in low for n in needles):
            return name
    return "generic"


def _to_cents(whole: str, cents: str | None) -> int:
    return int(whole.replace(",", "")) * 100 + int(cents or 0)


def _walk_jsonld(node: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(node, list):
        for item in node:
            out.extend(_walk_jsonld(item))
    elif isinstance(node, dict):
        out.append(node)
        for value in node.values():
            if isinstance(value, list | dict):
                out.extend(_walk_jsonld(value))
    return out


def _jsonld_price(soup: BeautifulSoup) -> tuple[int | None, str, str | None, str]:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue
        for node in _walk_jsonld(data):
            offers = node.get("offers")
            type_ = str(node.get("@type", ""))
            if type_ not in ("Vehicle", "Car", "Product") and offers is None:
                continue
            offer = offers[0] if isinstance(offers, list) and offers else offers
            if not isinstance(offer, dict) or "price" not in offer:
                continue
            raw = str(offer["price"]).replace(",", "")
            try:
                cents = round(float(raw) * 100)
            except ValueError:
                continue
            vin = node.get("vehicleIdentificationNumber")
            return cents, "jsonld", str(vin) if vin else None, str(node.get("name", ""))
    return None, "", None, ""


def extract_listing(url: str, html: str) -> Listing:
    """Extract a validated listing record from page HTML.

    Order: schema.org JSON-LD, then generic text near the price.

    Args:
        url: Page URL.
        html: Raw page HTML.

    Returns:
        A Listing. price_cents is None when no price was found.
    """
    soup = BeautifulSoup(html, "html.parser")
    cents, label, vin, name = _jsonld_price(soup)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:MAX_TEXT]
    prices = [
        f"${m.group(1)}" + (f".{m.group(2)}" if m.group(2) else "") for m in PRICE_RE.finditer(text)
    ]
    if cents is None and prices:
        first = PRICE_RE.search(text)
        if first:
            cents = _to_cents(first.group(1), first.group(2))
            label = "text"
    if vin is None:
        m = VIN_RE.search(text)
        vin = m.group(0) if m else None
    title = name or (soup.title.get_text(strip=True) if soup.title else "")
    disclaimers = " | ".join(m.group(0).strip() for m in DISCLAIMER_RE.finditer(text))[:2000]
    return Listing(
        url=url,
        vin=vin,
        title=title,
        price_cents=cents,
        price_label=label,
        all_prices=prices[:10],
        disclaimer_text=disclaimers,
        page_text=text,
        platform=detect_platform(html),
    )
