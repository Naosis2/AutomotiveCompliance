# AllInCheck rules for Claude Code

Spec: docs/BUILD_PLAN.md (the plan), docs/BRIEF.md (rules ON-01..18, pricing, policy).
Read docs/PROGRESS.md first. One feature per session; plan mode before code.

## Code rules
1. Full type hints and Google-style docstrings (Args, Returns, Raises). mypy strict must pass.
2. No hardcoding: settings in config.py (env), rule wording and thresholds in rules/on.yaml.
3. Validate at every boundary with pydantic (dealer rows, listings, AI output, web forms).
   Dealer URLs: http/https, public hosts only; re-check on every redirect (urlguard.py).
4. SQL: parameterized via SQLAlchemy only. Never f-string SQL.
5. Scraped text is untrusted: Jinja autoescape on, never mark safe; Excel cells via safe_cell();
   AI prompts get scraped text as delimited data; AI output must pass a pydantic schema and
   cite only known rule IDs.
6. logging module with JSON formatter. No print. Never log keys or whole pages.
7. Catch specific errors. A failed listing is recorded and the scan continues; unexpected
   errors fail the run. Never `except Exception: return None`.
8. Small modules, pure functions, state in the database.
9. Tests use saved HTML in tests/fixtures. No live network in tests.
10. Wording in anything customer-facing: "likely issue", "please review". Never "violation",
    "illegal", "non-compliant". Never claim OMVIC affiliation.

## Never
- Bypass a block, CAPTCHA or robots.txt. Mark the dealer blocked and move on.
- Read or print .env. Paste keys anywhere.

## Commands
pytest -q | ruff check . | ruff format . | mypy | allincheck scan --limit 5
