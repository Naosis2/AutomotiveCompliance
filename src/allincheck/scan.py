"""Run a scan over a list of dealers."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import ValidationError

from allincheck.config import Settings
from allincheck.discover import discover_listings
from allincheck.extract import extract_listing
from allincheck.fetch import BlockedError, FetchError, PoliteFetcher
from allincheck.models import Dealer, DealerResult, ScanError
from allincheck.rules import RuleSet, check_listing, group_site_wide
from allincheck.urlguard import UnsafeUrlError, check_public_url

log = logging.getLogger(__name__)


def load_dealers(path: Path) -> tuple[list[Dealer], list[str]]:
    """Read and validate data/dealers.csv.

    Args:
        path: CSV with columns name, website_url, province, notes.

    Returns:
        Valid dealers and a list of problems for rows that were skipped.
    """
    dealers: list[Dealer] = []
    problems: list[str] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for n, row in enumerate(csv.DictReader(fh), start=2):
            try:
                dealer = Dealer.model_validate(row)
                check_public_url(str(dealer.website_url))
                dealers.append(dealer)
            except (ValidationError, UnsafeUrlError) as exc:
                problems.append(f"row {n}: {type(exc).__name__}")
    return dealers, problems


def scan_dealer(
    dealer: Dealer,
    fetcher: PoliteFetcher,
    rules: RuleSet,
    settings: Settings,
    save_html_dir: Path | None = None,
) -> DealerResult:
    """Scan one dealer. A failed listing is recorded and the scan continues.

    Args:
        dealer: The dealer to scan.
        fetcher: Polite fetcher.
        rules: Rule set.
        settings: Settings.
        save_html_dir: If set, fetched listing pages are saved here as test fixtures.

    Returns:
        The dealer's result.
    """
    site = str(dealer.website_url)
    result = DealerResult(dealer=dealer.name, website_url=site)
    try:
        urls = discover_listings(fetcher, site, settings.max_listings_per_dealer)
    except BlockedError as exc:
        result.status = "blocked"
        result.errors.append(
            ScanError(
                dealer=dealer.name,
                url=site,
                stage="discover",
                error_type="blocked",
                message=str(exc),
            )
        )
        return result
    except FetchError as exc:
        result.status = "failed"
        result.errors.append(
            ScanError(
                dealer=dealer.name, url=site, stage="discover", error_type="fetch", message=str(exc)
            )
        )
        return result
    if not urls:
        result.errors.append(
            ScanError(
                dealer=dealer.name,
                url=site,
                stage="discover",
                error_type="no_listings",
                message="no listing links found",
            )
        )
    for url in urls:
        try:
            html = fetcher.get(url)
        except BlockedError as exc:
            result.status = "blocked"
            result.errors.append(
                ScanError(
                    dealer=dealer.name,
                    url=url,
                    stage="fetch",
                    error_type="blocked",
                    message=str(exc),
                )
            )
            break
        except FetchError as exc:
            result.errors.append(
                ScanError(
                    dealer=dealer.name,
                    url=url,
                    stage="fetch",
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            continue
        if save_html_dir is not None:
            save_html_dir.mkdir(parents=True, exist_ok=True)
            name = f"{urlsplit(site).hostname}_{abs(hash(url)) % 10**8}.html"
            (save_html_dir / name).write_text(html, encoding="utf-8")
        listing = extract_listing(url, html)
        if listing.price_cents is None:
            result.errors.append(
                ScanError(
                    dealer=dealer.name,
                    url=url,
                    stage="extract",
                    error_type="no_price_found",
                    message="no price found",
                )
            )
        result.platform = listing.platform if listing.platform != "generic" else result.platform
        result.listings.append(listing)
        result.findings.extend(check_listing(dealer.name, listing, rules))
    result.findings = group_site_wide(result.findings, settings.site_wide_threshold)
    return result
