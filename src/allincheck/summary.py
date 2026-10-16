"""Plain-text summary of one dealer scan, for a quick look during a demo or outreach."""

from __future__ import annotations

from allincheck.models import DealerResult

ORDER = {"high": 0, "medium": 1, "low": 2}


def summarize(result: DealerResult, note: str) -> str:
    """Build a short Markdown summary of a dealer scan.

    Args:
        result: The dealer's scan result.
        note: Disclaimer line from the rule set.

    Returns:
        Markdown text. Wording stays "likely issue / please review".
    """
    priced = sum(1 for li in result.listings if li.price_cents is not None)
    lines = [
        f"# Test scan: {result.dealer}",
        "",
        f"- Website: {result.website_url}",
        f"- Status: {result.status}",
        f"- Listings checked: {len(result.listings)} ({priced} with a price found)",
        f"- Pages that could not be read: {len(result.errors)}",
        f"- Likely issues: {sum(1 for f in result.findings if f.confidence == 'high')}",
        f"- Lower-confidence items to check by hand: "
        f"{sum(1 for f in result.findings if f.confidence == 'low')}",
        "",
    ]
    if result.status == "blocked":
        lines += ["The site blocked automated access, so this scan is incomplete.", ""]
    for f in sorted(result.findings, key=lambda x: (x.confidence != "high", ORDER[x.severity])):
        where = f.listing_url or f"site-wide ({f.listings_affected} listings)"
        lines += [
            f"## [{f.severity}{', check by hand' if f.confidence == 'low' else ''}] {f.title}",
            f"- Rule: {f.rule_id} {f.guideline_ref}".rstrip(),
            f"- Where: {where}",
            f'- Ad wording: "{f.evidence_text}"',
            f"- Suggested fix: {f.fix_hint}",
            "",
        ]
    if not result.findings:
        lines += ["No likely issues found in the pages that were read.", ""]
    lines += ["---", note, "Please review each item by hand before relying on it."]
    return "\n".join(lines)
