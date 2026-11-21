"""Download the latest 10-K filing for a company from SEC EDGAR.

Usage (PowerShell):
    $env:SEC_USER_AGENT = "Your Name you@example.com"
    uv run python scripts/download_10k.py --ticker AAPL --cik 320193

Saves to data/raw/<TICKER>/:
    <TICKER>_10-K_<report-date>.htm   the filing (inline XBRL HTML)
    <TICKER>_10-K_<report-date>.json  provenance metadata

TODO (Phase 3): move into src/fin_rag/, use logging + config instead of print/constants.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
RAW_DIR = Path("data/raw")


def find_latest_10k(submissions: dict) -> dict:
    """Return details of the most recent 10-K in the company's submissions JSON."""
    recent = submissions["filings"]["recent"]
    # EDGAR lists recent filings newest-first, as parallel arrays.
    for i, form in enumerate(recent["form"]):
        if form == "10-K":
            return {
                "accession_number": recent["accessionNumber"][i],
                "primary_document": recent["primaryDocument"][i],
                "filing_date": recent["filingDate"][i],
                "report_date": recent["reportDate"][i],
            }
    raise ValueError("No 10-K found in recent filings.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the latest 10-K from SEC EDGAR.")
    parser.add_argument("--ticker", required=True, help="Ticker symbol, e.g. AAPL")
    parser.add_argument("--cik", required=True, type=int, help="SEC CIK number, e.g. 320193")
    args = parser.parse_args()
    ticker = args.ticker.upper()

    user_agent = os.environ.get("SEC_USER_AGENT")
    if not user_agent:
        print(
            "ERROR: SEC_USER_AGENT is not set. In PowerShell run:\n"
            '  $env:SEC_USER_AGENT = "Your Name you@example.com"',
            file=sys.stderr,
        )
        return 1

    headers = {"User-Agent": user_agent}
    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        # 1. Find the latest 10-K
        resp = client.get(SUBMISSIONS_URL.format(cik=args.cik))
        resp.raise_for_status()
        submissions = resp.json()
        filing = find_latest_10k(submissions)
        print(f"Company: {submissions.get('name')}")
        print(f"Latest 10-K: period ending {filing['report_date']}, filed {filing['filing_date']}")

        # 2. Work out output paths; skip if already downloaded (idempotent)
        out_dir = RAW_DIR / ticker
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{ticker}_10-K_{filing['report_date']}"
        doc_path = out_dir / f"{stem}.htm"
        meta_path = out_dir / f"{stem}.json"
        if doc_path.exists() and meta_path.exists():
            print(f"Already downloaded, skipping: {doc_path}")
            return 0

        # 3. Download the filing
        url = ARCHIVE_URL.format(
            cik=args.cik,
            accession=filing["accession_number"].replace("-", ""),
            document=filing["primary_document"],
        )
        time.sleep(0.2)  # stay well under SEC's 10 requests/second limit
        doc = client.get(url)
        doc.raise_for_status()
        doc_path.write_bytes(doc.content)

        # 4. Save provenance metadata alongside it
        metadata = {
            "ticker": ticker,
            "company_name": submissions.get("name"),
            "cik": args.cik,
            "form": "10-K",
            **filing,
            "source_url": url,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "size_bytes": len(doc.content),
        }
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Saved: {doc_path} ({len(doc.content) / 1_000_000:.1f} MB)")
    print(f"Saved: {meta_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())