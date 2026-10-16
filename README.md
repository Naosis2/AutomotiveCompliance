# AllInCheck (V1: Phase 0 scanner)

Scans the websites of signed-up Ontario dealers (and one-off test scans you start by hand) and writes an Excel workbook of likely advertised-price issues.

## Run in the cloud (no install)
1. Put dealers in `data/dealers.csv` (name, website_url, province, notes).
2. Add repo secret `ALLINCHECK_CONTACT_EMAIL` (sent in the User-Agent).
3. Actions tab > scan > Run workflow. Download `allincheck-results` from the run page.
   Tick "save_html" once to collect pages for test fixtures.

## Test scan of one website (demo or outreach research)
Actions tab > audit > Run workflow > enter the dealer's website address.
The run page shows a summary; download `audit-results` for the Excel file.
Locally: `allincheck audit https://dealer.ca` writes `out/dealer.ca/summary.md` and `results.xlsx`.
Scans only the address you give it, politely, and stops if the site blocks it.

## Run locally
    pip install -e ".[dev]"
    allincheck scan --dealers data/dealers.csv --limit 5
    pytest -q && ruff check . && mypy

## Status
See docs/PROGRESS.md. Rules in `rules/on.yaml` are DRAFT placeholders until mapped to the brief.
