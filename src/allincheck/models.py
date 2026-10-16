"""Validated data shapes shared across the scanner."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

Severity = Literal["high", "medium", "low"]
FindingSource = Literal["regex", "ai", "both"]


class Dealer(BaseModel):
    """One row of data/dealers.csv."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    website_url: HttpUrl
    province: str = Field(min_length=2, max_length=2)
    notes: str = ""


class Listing(BaseModel):
    """A vehicle listing extracted from one page."""

    url: str
    vin: str | None = None
    title: str = ""
    price_cents: int | None = None
    price_label: str = ""
    all_prices: list[str] = Field(default_factory=list)
    disclaimer_text: str = ""
    page_text: str = ""
    platform: str = "generic"


class Finding(BaseModel):
    """A likely issue found on a listing or site-wide."""

    dealer: str
    rule_id: str
    rule_version: int
    title: str
    severity: Severity
    confidence: Literal["high", "low"] = "high"
    source: FindingSource = "regex"
    listing_url: str | None = None
    evidence_text: str
    matched: str = ""
    guideline_ref: str = ""
    fix_hint: str = ""
    listings_affected: int = 1


class ScanError(BaseModel):
    """A page or stage that could not be completed."""

    dealer: str
    url: str
    stage: Literal["discover", "fetch", "extract", "check"]
    error_type: str
    message: str


class DealerResult(BaseModel):
    """Everything one dealer's scan produced."""

    dealer: str
    website_url: str
    platform: str = "generic"
    status: Literal["ok", "blocked", "failed"] = "ok"
    listings: list[Listing] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    errors: list[ScanError] = Field(default_factory=list)
