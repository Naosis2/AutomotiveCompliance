"""Build the results workbook. Scraped text is always written as a safe string."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from allincheck.models import DealerResult
from allincheck.rules import RuleSet

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
MAX_CELL = 2000


def safe_cell(value: Any) -> Any:
    """Make a value safe to write into a spreadsheet cell.

    Strings starting with a formula character get a leading apostrophe-style space
    prefix so Excel treats them as text; long strings are cut.

    Args:
        value: Any cell value.

    Returns:
        A value safe for openpyxl.
    """
    if isinstance(value, str):
        text = value[:MAX_CELL]
        if text.startswith(FORMULA_PREFIXES):
            text = "'" + text
        return text
    return value


def _sheet(ws: Worksheet, header: list[str], rows: list[list[Any]], widths: list[int]) -> None:
    ws.append(header)
    for row in rows:
        ws.append([safe_cell(v) for v in row])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w


def build_workbook(
    results: list[DealerResult], rules: RuleSet, path: Path, scan_date: datetime | None = None
) -> None:
    """Write the results workbook.

    Args:
        results: One result per dealer.
        rules: The rule set used.
        path: Output .xlsx path.
        scan_date: Timestamp for the Summary sheet (defaults to now, UTC).
    """
    when = scan_date or datetime.now(UTC)
    wb = Workbook()
    summary = wb.active
    assert summary is not None  # noqa: S101
    summary.title = "Summary"
    counts: dict[str, dict[str, int]] = {}
    for r in results:
        for f in r.findings:
            c = counts.setdefault(f.rule_id, {"title": 0, "n": 0})
            c["n"] += f.listings_affected
    rows = [
        [rule.id, rule.title, rule.severity, counts.get(rule.id, {}).get("n", 0)]
        for rule in rules.rules
    ]
    _sheet(summary, ["Rule ID", "Title", "Severity", "Listings affected"], rows, [18, 60, 12, 18])
    summary.insert_rows(1, 2)
    summary["A1"] = "Scan date"
    summary["B1"] = when.replace(tzinfo=None)
    summary["A2"] = "Dealers scanned"
    summary["B2"] = len(results)
    summary.freeze_panes = "A4"

    ws = wb.create_sheet("Findings")
    f_rows = [
        [
            f.dealer,
            f.listing_url or "(site-wide)",
            f.rule_id,
            f.title,
            f.severity,
            f.confidence,
            f.listings_affected,
            f.evidence_text,
            f.fix_hint,
        ]
        for r in results
        for f in r.findings
        if f.confidence == "high"
    ]
    _sheet(
        ws,
        [
            "Dealer",
            "Link",
            "Rule ID",
            "Rule title",
            "Severity",
            "Confidence",
            "Listings affected",
            "Evidence",
            "Suggested fix",
            "Label (yes/no/unsure)",
        ],
        [row + [""] for row in f_rows],
        [24, 50, 16, 40, 10, 12, 16, 70, 40, 20],
    )

    ws = wb.create_sheet("To review")
    t_rows = [
        [
            f.dealer,
            f.listing_url or "(site-wide)",
            f.rule_id,
            f.title,
            f.severity,
            f.confidence,
            f.listings_affected,
            f.evidence_text,
            f.fix_hint,
        ]
        for r in results
        for f in r.findings
        if f.confidence == "low"
    ]
    _sheet(
        ws,
        [
            "Dealer",
            "Link",
            "Rule ID",
            "Rule title",
            "Severity",
            "Confidence",
            "Listings affected",
            "Evidence",
            "Suggested fix",
            "Label (yes/no/unsure)",
        ],
        [row + [""] for row in t_rows],
        [24, 50, 16, 40, 10, 12, 16, 70, 40, 20],
    )

    ws = wb.create_sheet("Listings")
    l_rows = [
        [
            r.dealer,
            li.url,
            li.title,
            li.vin or "",
            (li.price_cents / 100) if li.price_cents is not None else "",
            li.price_label,
            li.platform,
        ]
        for r in results
        for li in r.listings
    ]
    _sheet(
        ws,
        ["Dealer", "Link", "Title", "VIN", "Price (CAD)", "Price source", "Platform"],
        l_rows,
        [24, 50, 40, 20, 14, 14, 16],
    )

    ws = wb.create_sheet("Errors")
    e_rows = [
        [e.dealer, e.url, e.stage, e.error_type, e.message] for r in results for e in r.errors
    ]
    e_rows += [
        [r.dealer, r.website_url, "discover", r.status, "dealer " + r.status]
        for r in results
        if r.status != "ok"
    ]
    _sheet(ws, ["Dealer", "Link", "Stage", "Reason", "Message"], e_rows, [24, 50, 12, 24, 50])

    ws = wb.create_sheet("Rules")
    _sheet(
        ws,
        ["Rule ID", "Title", "Severity", "Version", "Guideline reference"],
        [[r.id, r.title, r.severity, r.version, r.guideline_ref] for r in rules.rules],
        [18, 60, 12, 10, 50],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
