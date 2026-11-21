# Chapter 3 — Parsing: HTML → clean text with page numbers

## Key ideas
- Parsing = separating the words from the HTML formatting (tags). Everything downstream
  (chunking, embedding, retrieval) only ever sees what the parser outputs: garbage in, garbage out.
- A 10-K HTML file is ~85% markup: 1.65M chars of HTML → ~234K chars of text.
- HTML tags come in two kinds:
  - block tags (<p>, <div>, <tr>) = real line breaks
  - inline tags (<span>) = styling inside a line; must NOT break the line
- Tables in 10-Ks are often invisible (no borders); still real <table>/<tr>/<td> in the HTML.
  Even the cover page uses tables just for layout.
- HTML has no pages, but 10-Ks contain print markers: <hr style="page-break-after:always"/>.
  Apple FY2026: 64 markers → 65 pages.
- Parse once, save, reuse (JSONL = one JSON record per line). Re-parse only with --force.

## How the parser evolved (iteration story)
**v1 — Strip all tags** (get_text with separator="\n")
- Saw: only ~15% of the file is text.
- Saw: output started with junk: fasb.org/us-gaap/2026#LongTermDebtCurrent, aapl:...Member
- Why: inline XBRL has a hidden (display:none) block of machine-readable tags. Browsers hide it;
  BeautifulSoup extracts all text, visible or not.
- Risk: junk chunks would match "long-term debt" queries but contain no answer.

**v2 — Remove hidden elements first** (find display:none → decompose())
- Saw: 77 hidden blocks removed, ~14K junk chars gone; text starts at the real cover page.
- New problem: lines broken apart: "FORM / 10-K", "(408 / ) / 996-1010"
- Why: separator="\n" adds a newline between EVERY tag, including inline <span>s.

**v3 — Newlines only after block tags; " | " between table cells**
- Saw: clean lines; table rows on one line:
  Total net sales | $ | 478,834 | ... | 416,161 | ... | 391,035
- Weakness: years sit in the header row, not the data row. If chunking separates them, the LLM
  gets numbers without years → may answer wrong even when retrieval is right.
- Also: the same figure appears on several pages (MD&A, segments, income statement), so near-duplicate chunks are likely.

**v4 — Split into pages + read printed page numbers from the footer**
- Checked first: counted page-break markers (64), all the same tag.
- Saw: our page 29 = printed page 27 → offset of 2 (cover + table of contents unnumbered).
  Citations would have been wrong.
- Fix: read the number from the footer ("Apple Inc. | 2026 Form 10-K | 27"), store both
  page (position) and printed_page (for citations), and remove the footer line (boilerplate noise).
- Result: pages w/o footer = [1, 2] exactly; ~2K chars of repeated footer removed.

## Questions I asked
**Q: When I open the file in the browser I don't see any tables?**
A: They're invisible (no borders), so they look like aligned text. Ctrl+F "Total net sales", then
right-click → Inspect: the number sits in a <td> inside a <tr> inside a <table>.
(I had also opened the wrong file: Apple Hospitality REIT's Exhibit 21.1, a subsidiaries list.)

**Q: `hidden` stores the elements, so are they actually deleted from `text`?**
A: `hidden` holds pointers to elements INSIDE the soup, not copies. decompose() deletes them
from the soup itself. text is a snapshot taken when get_text() runs, so ORDER matters:
delete first, then extract. Proof: "fasb.org/us-gaap" in text → False.

## Gotchas
- XMLParsedAsHTMLWarning: harmless; inline XBRL starts with an XML declaration. Silence it with warnings.filterwarnings.
- Searching "Total net sales" also matches sentences, not just table rows (8 pages vs 5 rows).
- Page sizes vary 10× (719 → 7,118 chars), so pages are a bad retrieval unit → chunking next.
- FOOTER_RE is tuned to Apple's format; check it on other companies (Phase 3).

## Commands I used
uv add beautifulsoup4 lxml
uv run python scripts/parse_10k.py --ticker AAPL [--force]
(Select-String -Path <file> -Pattern "page-break-(before|after)\s*:\s*always" -AllMatches).Matches.Count
Get-Content data\parsed\AAPL\*.jsonl | ConvertFrom-Json | Where-Object page -eq 29 | Select-Object page, printed_page

## Interview version
"I didn't trust the parser blindly; I inspected output at every step. The first pass leaked
hidden XBRL metadata, so I stripped display:none elements. Inline spans were fragmenting lines,
so I switched to block-aware line breaks and kept table rows intact. When splitting into pages
I checked citations against the printed document, found a 2-page offset, and fixed it by
reading page numbers from the footer instead of hard-coding an offset. I logged the remaining
weakness, table headers separated from data rows, to measure once I had evals."
