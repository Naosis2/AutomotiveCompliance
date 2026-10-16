"""Command line entry point: allincheck scan."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import ValidationError

from allincheck.config import Settings, get_settings
from allincheck.excel import build_workbook
from allincheck.fetch import PoliteFetcher
from allincheck.logging_setup import setup_logging
from allincheck.models import Dealer
from allincheck.rules import RuleSet, load_rules
from allincheck.scan import load_dealers, scan_dealer
from allincheck.summary import summarize
from allincheck.urlguard import UnsafeUrlError, check_public_url

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Argument list (defaults to sys.argv).

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(prog="allincheck")
    sub = parser.add_subparsers(dest="cmd", required=True)
    scan = sub.add_parser("scan", help="scan dealers and write results.xlsx")
    scan.add_argument("--dealers", type=Path, default=Path("data/dealers.csv"))
    scan.add_argument("--rules", type=Path, default=Path("rules/on.yaml"))
    scan.add_argument("--out", type=Path, default=Path("out"))
    scan.add_argument("--limit", type=int, default=None, help="scan only the first N dealers")
    scan.add_argument("--save-html", action="store_true", help="save fetched pages to out/html")
    audit = sub.add_parser("audit", help="one-off test scan of a single dealer website")
    audit.add_argument("url", help="dealer website address, e.g. https://dealer.ca")
    audit.add_argument("--name", default=None, help="dealer name (defaults to the hostname)")
    audit.add_argument("--rules", type=Path, default=Path("rules/on.yaml"))
    audit.add_argument("--out", type=Path, default=Path("out"))
    audit.add_argument("--save-html", action="store_true")
    args = parser.parse_args(argv)

    setup_logging()
    settings = get_settings()
    rules = load_rules(args.rules)
    if args.cmd == "audit":
        return _audit(args, settings, rules)
    dealers, problems = load_dealers(args.dealers)
    for p in problems:
        log.warning("dealer row skipped", extra={"ctx": {"problem": p}})
    if args.limit:
        dealers = dealers[: args.limit]
    fetcher = PoliteFetcher(settings)
    results = []
    try:
        for dealer in dealers:
            log.info("scanning", extra={"ctx": {"dealer": dealer.name}})
            results.append(
                scan_dealer(
                    dealer, fetcher, rules, settings, args.out / "html" if args.save_html else None
                )
            )
    finally:
        fetcher.close()
    args.out.mkdir(parents=True, exist_ok=True)
    build_workbook(results, rules, args.out / "results.xlsx")
    (args.out / "results.json").write_text(
        json.dumps([r.model_dump(exclude={"listings"}) for r in results], indent=2),
        encoding="utf-8",
    )
    log.info("done", extra={"ctx": {"dealers": len(results)}})
    return 0


def _audit(args: argparse.Namespace, settings: Settings, rules: RuleSet) -> int:
    """Scan one website on demand and write results.xlsx and summary.md.

    Args:
        args: Parsed arguments (url, name, out, save_html).
        settings: Application settings.
        rules: Rule set.

    Returns:
        Exit code: 0 on success, 2 if the URL is not a public http/https address.
    """
    url = args.url if "://" in args.url else f"https://{args.url}"
    try:
        check_public_url(url)
        dealer = Dealer(
            name=args.name or urlsplit(url).hostname or url, website_url=url, province="ON"
        )
    except (UnsafeUrlError, ValidationError) as exc:
        log.error("bad url", extra={"ctx": {"why": str(exc)}})
        return 2
    out = args.out / (urlsplit(url).hostname or "site")
    fetcher = PoliteFetcher(settings)
    try:
        result = scan_dealer(
            dealer, fetcher, rules, settings, out / "html" if args.save_html else None
        )
    finally:
        fetcher.close()
    out.mkdir(parents=True, exist_ok=True)
    build_workbook([result], rules, out / "results.xlsx")
    (out / "summary.md").write_text(summarize(result, rules.guideline_note), encoding="utf-8")
    log.info("audit done", extra={"ctx": {"findings": len(result.findings), "out": str(out)}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
