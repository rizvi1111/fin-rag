"""Naive parser: 10-K HTML -> clean text, one record per printed page.

Usage (PowerShell):
    uv run python scripts/parse_10k.py --ticker AAPL
    uv run python scripts/parse_10k.py --ticker AAPL --force   # re-parse even if saved

Reads  data/raw/<TICKER>/*.htm   (+ matching .json metadata from the downloader)
Writes data/parsed/<TICKER>/<same-name>.jsonl   (one JSON record per page)

Known shortcuts (TODO Phase 3):
- table header rows (years) can be separated from data rows
- no section detection (Item 1A, Item 7, Item 8 ...)
- footer pattern is tuned to Apple's format ("... Form 10-K | 27"); check other companies
- move into src/fin_rag/, use logging + config
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import warnings
from pathlib import Path

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# The 10-K starts like an XML file; we parse it as HTML on purpose, so hide the warning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

RAW_DIR = Path("data/raw")
PARSED_DIR = Path("data/parsed")

# The whole tag that marks a printed page break, e.g. <hr style="page-break-after:always"/>
PAGE_BREAK_RE = re.compile(r"<[^>]*page-break-(?:before|after)\s*:\s*always[^>]*>", re.IGNORECASE)
HIDDEN_RE = re.compile(r"display\s*:\s*none", re.IGNORECASE)
BLOCK_TAGS = ["p", "div", "tr", "br", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6"]

# v4: footer line at the bottom of each printed page, e.g. "Apple Inc. | 2026 Form 10-K | 27"
FOOTER_RE = re.compile(r"Form 10-K\s*\|\s*(\d+)\s*$", re.IGNORECASE)


def html_to_text(html: str) -> str:
    """The v3 cleaning logic: one HTML piece in, clean text out."""
    soup = BeautifulSoup(html, "lxml")

    # v2: remove hidden content (the inline XBRL block)
    for tag in soup.find_all(style=HIDDEN_RE):
        tag.decompose()
    for tag in soup(["script", "style", "title"]):
        tag.decompose()

    # v3: newlines only after block tags, " | " between table cells
    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_after("\n")
    for cell in soup.find_all(["td", "th"]):
        cell.insert_after(" | ")

    text = soup.get_text(separator="")

    lines = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line)            # many spaces -> one
        line = re.sub(r"(\s*\|\s*)+", " | ", line)  # empty cells "| | |" -> " | "
        line = line.strip(" |")
        if line:
            lines.append(line)
    return "\n".join(lines)


def split_footer(text: str) -> tuple[str, int | None]:
    """v4: if the last line is the page footer, remove it and return the printed page number."""
    lines = text.split("\n")
    match = FOOTER_RE.search(lines[-1])
    if match:
        return "\n".join(lines[:-1]), int(match.group(1))
    return text, None  # no footer (e.g. cover page, table of contents)


def parse_filing(html_path: Path, metadata: dict) -> list[dict]:
    """Cut the filing at page breaks and return one record per non-empty page."""
    html = html_path.read_text(encoding="utf-8", errors="replace")
    pieces = PAGE_BREAK_RE.split(html)  # 64 breaks -> 65 pieces

    records = []
    for page_num, piece in enumerate(pieces, start=1):
        text = html_to_text(piece)
        if not text:
            continue  # skip blank pages, but keep numbering aligned with the breaks
        text, printed_page = split_footer(text)  # v4
        records.append(
            {
                "doc_id": html_path.stem,
                "ticker": metadata.get("ticker"),
                "company_name": metadata.get("company_name"),
                "form": metadata.get("form"),
                "report_date": metadata.get("report_date"),
                "source_url": metadata.get("source_url"),
                "page": page_num,
                "printed_page": printed_page,  # v4: what humans see; use this for citations
                "n_chars": len(text),
                "text": text,
            }
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse downloaded 10-K HTML into per-page text.")
    parser.add_argument("--ticker", required=True, help="Ticker symbol, e.g. AAPL")
    parser.add_argument("--force", action="store_true", help="Re-parse even if output exists")
    args = parser.parse_args()
    ticker = args.ticker.upper()

    html_files = sorted((RAW_DIR / ticker).glob("*.htm"))
    if not html_files:
        print(f"ERROR: no .htm files in {RAW_DIR / ticker}. Run download_10k.py first.", file=sys.stderr)
        return 1

    out_dir = PARSED_DIR / ticker
    out_dir.mkdir(parents=True, exist_ok=True)

    for html_path in html_files:
        out_path = out_dir / f"{html_path.stem}.jsonl"
        if out_path.exists() and not args.force:
            print(f"Already parsed, skipping: {out_path}  (use --force to re-parse)")
            continue

        meta_path = html_path.with_suffix(".json")
        metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

        records = parse_filing(html_path, metadata)
        with out_path.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        total_chars = sum(r["n_chars"] for r in records)
        biggest = max(records, key=lambda r: r["n_chars"])
        no_footer = [r["page"] for r in records if r["printed_page"] is None]  # v4
        print(f"Parsed: {html_path.name}")
        print(f"  pages with text   : {len(records)}")
        print(f"  total text        : {total_chars:,} chars")
        print(f"  longest page      : p.{biggest['page']} ({biggest['n_chars']:,} chars)")
        print(f"  pages w/o footer  : {no_footer}")  # v4
        print(f"  saved             : {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())