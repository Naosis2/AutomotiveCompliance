"""Load rules from YAML and run them over listing text."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from allincheck.models import Finding, Listing, Severity

SNIPPET_RADIUS = 80


class Rule(BaseModel):
    """One pattern rule."""

    id: str
    title: str
    severity: Severity
    confidence: Literal["high", "low"] = "high"
    version: int
    guideline_ref: str = ""
    patterns: list[str]
    exempt_patterns: list[str] = Field(default_factory=list)
    required_present_patterns: list[str] = Field(default_factory=list)
    required_absent_patterns: list[str] = Field(default_factory=list)
    message: str
    fix_hint: str = ""


class RuleSet(BaseModel):
    """The rules file."""

    version: int
    effective_date: str
    guideline_note: str
    rules: list[Rule]


def load_rules(path: Path) -> RuleSet:
    """Load and validate a rules YAML file.

    Args:
        path: Path to rules YAML.

    Returns:
        The validated rule set.

    Raises:
        ValueError: If the file does not match the schema or a regex is invalid.
    """
    ruleset = RuleSet.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    for rule in ruleset.rules:
        all_patterns = (
            rule.patterns
            + rule.exempt_patterns
            + rule.required_present_patterns
            + rule.required_absent_patterns
        )
        for pat in all_patterns:
            re.compile(pat)
    return ruleset


def check_listing(dealer: str, listing: Listing, rules: RuleSet) -> list[Finding]:
    """Run all rules over one listing.

    Args:
        dealer: Dealer name.
        listing: Extracted listing.
        rules: Rule set.

    Returns:
        Findings for this listing.
    """
    findings: list[Finding] = []
    text = listing.page_text
    for rule in rules.rules:
        cleaned = text
        for ex in rule.exempt_patterns:
            cleaned = re.sub(ex, " ", cleaned, flags=re.IGNORECASE)
        match = None
        for pat in rule.patterns:
            match = re.search(pat, cleaned, flags=re.IGNORECASE)
            if match:
                break
        if match is None:
            continue
        if not all(
            re.search(p, cleaned, flags=re.IGNORECASE) for p in rule.required_present_patterns
        ):
            continue
        if any(re.search(p, cleaned, flags=re.IGNORECASE) for p in rule.required_absent_patterns):
            continue
        start = max(0, match.start() - SNIPPET_RADIUS)
        snippet = cleaned[start : match.end() + SNIPPET_RADIUS].strip()
        findings.append(
            Finding(
                dealer=dealer,
                rule_id=rule.id,
                rule_version=rule.version,
                title=rule.title,
                severity=rule.severity,
                confidence=rule.confidence,
                listing_url=listing.url,
                evidence_text=snippet,
                matched=re.sub(r"\s+", " ", match.group(0).lower()),
                guideline_ref=rule.guideline_ref,
                fix_hint=rule.fix_hint,
            )
        )
    return findings


def group_site_wide(findings: list[Finding], threshold: int) -> list[Finding]:
    """Collapse repeated findings into one site-wide finding per rule.

    A rule that flags the same matched wording on `threshold` or more listings becomes
    one finding with no listing URL; the rest stay per-listing.

    Args:
        findings: Per-listing findings for one dealer.
        threshold: Listings needed to call it site-wide.

    Returns:
        Site-wide findings followed by the remaining per-listing findings.
    """
    by_key: dict[tuple[str, str], list[Finding]] = defaultdict(list)
    for f in findings:
        by_key[(f.rule_id, f.matched)].append(f)
    site_wide: list[Finding] = []
    rest: list[Finding] = []
    for group in by_key.values():
        if len(group) >= threshold:
            head = group[0].model_copy(
                update={"listing_url": None, "listings_affected": len(group)}
            )
            site_wide.append(head)
        else:
            rest.extend(group)
    return site_wide + rest
