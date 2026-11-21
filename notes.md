# fin-rag — Study Notes

---

# Chapter 1 — Project setup: uv, Git, GitHub

## Key ideas
- **Reproducibility first.** Anyone (or CI) who clones the repo should get the exact same
  environment with one command: `uv sync`.
- **uv** manages Python versions, virtual environments and dependencies in one fast tool.
  Alternatives: pip+venv (no lockfile), Poetry (slower, no Python management), conda (heavy).
- **src layout** (src/fin_rag/): tests run against the *installed* package, which catches import bugs early.
- **Files uv creates:**
  - `pyproject.toml`: the project's single config file: name, dependencies, scripts, tool settings.
    You edit it (deps via `uv add` / `uv remove`).
  - `uv.lock`: exact resolved versions + hashes of every package. Written by uv, never hand-edited, committed.
  - `.python-version`: pins the Python used for development here (3.12).
  - `.venv/`: the actual installed environment. Machine-specific, disposable, never committed.
- **pyproject.toml vs uv.lock** = intent vs exact state (like a table's DDL vs a snapshot of
  installed state; like package.json vs package-lock.json).
- **One name, three forms:** `fin-rag` (project name, hyphen) → `fin_rag` (Python package, underscore,
  since identifiers can't contain hyphens) → `fin-rag` (command run with `uv run fin-rag`).
- **.gitignore before the first commit.** Secrets, data, models and vector DBs must never enter
  history, because removing them later is painful.
- **.gitattributes** (`* text=auto eol=lf`) puts line-ending rules in the repo itself, so Windows
  dev and Linux CI/Docker behave the same.
- **Commit email is public.** Use GitHub's noreply address (Settings → Emails → Keep private).

## What went wrong along the way (iteration story)
1. `uv run fin-rag` → "program not found". The folder was empty: `uv init` had never run there.
   (`uv run python --version` still worked, because uv finds Python even without a project.)
   Fix: `uv init --package --name fin-rag --python 3.12` in the current folder.
2. **Hardlink warning.** uv's cache was on C:, the project on D:, and hardlinks can't cross drives,
   so packages were copied instead (slow, double disk use; matters later for PyTorch ~1 GB).
   - Env var `UV_CACHE_DIR` didn't take effect (terminal sessions only read env vars at start).
   - Fix that worked: uv's own config file `%APPDATA%\uv\uv.toml` with `cache-dir = "D:\\uv-cache"`.
     uv reads it on every run, so no restart is needed.
3. **LF → CRLF warnings on `git add`.** Git for Windows rewrites line endings. Fixed with
   `.gitattributes` + `git add --renormalize .`
4. **Switched GitHub account** (rizvi1111). Put the username in the remote URL so Git Credential
   Manager picks the right login: `https://rizvi1111@github.com/rizvi1111/fin-rag.git`
5. **"Repository not found" on push.** The repo didn't exist on GitHub yet. Git never creates it for you.
6. **Old personal email leaked in pyproject.toml.** The edit had never been saved, and the file
   was already pushed publicly. Fix: rewrite history with an orphan branch + force push
   (safe only because it's a solo repo; never force-push shared branches).

## Questions I asked
**Q: What is fin-rag?**
A: Just the project name I chose ("financial RAG"). Not a tool or library. Could be anything.

**Q: What is pyproject.toml?**
A: The project's single config file (PEP 621 standard): what the project is, its dependencies,
its commands, and later tool settings ([tool.ruff], [tool.pytest]). Replaces setup.py,
requirements.txt etc. TOML = `[sections]` with `key = value`.

**Q: I don't see python-version in uv.lock?**
A: It's a separate file (`.python-version`). The lock records `requires-python` (the supported
*range*) because the resolution must be valid for every version in that range, not just my laptop's.
Also: `source = { editable = "." }` = my own package installed in editable mode, so code edits
apply immediately with no reinstall.

**Q: (check) Why commit uv.lock but not .venv?**
A: .venv is machine-specific (Windows binaries, absolute paths), large and disposable. The lock is
the recipe that rebuilds an identical .venv anywhere with `uv sync`. Commit the recipe, not the meal.

**Q: (check) .python-version vs requires-python?**
A: .python-version = what I *develop on* (a pin). requires-python = what the package *supports*
(a constraint used by the resolver and installers). Not a boolean. The pin must sit inside the range.

**Q: (check) Why create the GitHub repo empty?**
A: If GitHub adds a README it makes its own first commit → two unrelated histories → push rejected.

**Q: (check) Why run git status before committing if .gitignore exists?**
A: .gitignore only blocks patterns you anticipated; status is the last look before something
enters history forever. Also .gitignore doesn't affect already-tracked files.

## Gotchas
- PowerShell 5.1: no `&&`; `echo ... > file` writes **UTF-16** (git can't read it) → use an editor.
- `git add --renormalize` needs the dot: `git add --renormalize .`
- Text meant for a file (e.g. `cache-dir = "..."`) isn't a terminal command. Blocks are labelled **Terminal** or **File**.
- OS build 26100 = Windows 11, not 10 (check with `winver`; update the constraints doc).

## Commands I used
uv init --package --name fin-rag --python 3.12
uv run fin-rag
uv sync / uv add <pkg> / uv cache dir
git config --global user.email "<id>+<user>@users.noreply.github.com"
git add . ; git status ; git commit -m "..." ; git push -u origin main
git checkout --orphan clean-main   (history rewrite)

## Interview version
"I set the project up for reproducibility from commit one: uv with a committed lockfile so any
machine or CI runner rebuilds the exact environment, a src layout so tests hit the installed
package, and a .gitignore/.gitattributes baseline that keeps secrets, data and vector indexes out
of history and normalises line endings across Windows and Linux."

---

# Chapter 2 — Downloading the 10-K from SEC EDGAR

## Key ideas
- A **10-K** is a company's annual report filed with the SEC. EDGAR is the SEC's filing system.
- The script **automates the browser clicks**: search company → list filings → pick newest 10-K
  → open main document → save it.
- **CIK** = the SEC's permanent company ID. Names and tickers aren't unique
  ("Apple" also matches Apple Hospitality REIT), but CIKs are. Apple Inc. = 320193.
- **Two versions of the same data:** the EDGAR website (for humans) and
  `data.sec.gov/submissions/CIK##########.json` (for code). A web address designed for code = an **API**.
- **A filing is an envelope:** the main 10-K document + exhibits (EX-21 = subsidiaries list,
  EX-31/32 = CEO/CFO sign-offs). `primaryDocument` always points to the main 10-K.
- **HTML, not PDF:** EDGAR's official format is HTML (inline XBRL); tables stay as real tables.
- **SEC fair access:** every request needs a User-Agent header (name + email); max 10 requests/sec.
- **Licensing:** SEC filings are public US government records, fine to use. Still kept out of git
  (size; data ≠ code).
- This filing (FY ending 2026-09-26, filed 2026-11-03) is **after any local LLM's training
  cutoff**, so correct answers must come from retrieval, not model memory. Good demo point.

## How the script works (the story)
1. **Imports** = taking tools out of the toolbox. All built-in except `httpx` (needs `uv add`).
2. **Settings** = URL templates with blanks: `CIK{cik:010d}` → `CIK0000320193` (pad to 10 digits).
3. **find_latest_10k()**: the filings list is stored **by column** (parallel arrays: form[],
   accessionNumber[], primaryDocument[]...). Position `i` lines them up. Walk `form` with
   `enumerate`, stop at the first "10-K", read row `i` from the other columns.
   Hidden assumption: EDGAR sorts newest-first.
4. **main(), checks:** argparse reads `--ticker` / `--cik` (mandatory, CIK must be a number);
   fail fast if SEC_USER_AGENT is missing.
5. **main(), fetching:** `httpx.Client` (headers, 30s timeout, follow redirects) → GET the filings
   list → `raise_for_status()` (stop on 403/404) → `.json()` → find the 10-K → print company name
   as a sanity check.
6. **main(), saving:** build filename from report date → skip if already downloaded (idempotent)
   → fill in the archive URL (CIK unpadded, accession without dashes) → sleep 0.2s → download →
   save bytes untouched → write the metadata JSON.
7. **Start button:** `if __name__ == "__main__": sys.exit(main())`, which returns 0/1 to PowerShell.

## Three files in the story
| What | Source | Saved? |
|---|---|---|
| Filings list (JSON) | Downloaded from SUBMISSIONS_URL | No: used to find the 10-K, then dropped (4 values copied into metadata) |
| The 10-K (.htm) | Downloaded from ARCHIVE_URL | Yes → data/raw/AAPL/ |
| Metadata (.json) | **Written by our script** | Yes: provenance (source URL, accession, dates, download time) |

## What went wrong along the way
- `ModuleNotFoundError: httpx` → `uv add httpx` had never run (`dependencies = []`).
  `uv run` only installs what pyproject.toml lists.
- Opened a link with spaces around the slashes → `%20` in the URL → "Access Denied".
- Opened the wrong document: CIK 1418121 = Apple Hospitality REIT, and `ex21_1.htm` = an exhibit.

## Questions I asked
**Q: Is the 10-K available as a file on the web?**
A: Yes, it's a web page on sec.gov (EDGAR search → Apple Inc. → filter 10-K → main document).
The script automates exactly those clicks. The metadata's `source_url` opens the same page.

**Q: Is this the 10-K? .../data/1418121/000095017025025638/aple-ex21_1.htm**
A: No. Read it with the template {cik}/{accession}/{document}: 1418121 = Apple Hospitality REIT;
ex21_1 = Exhibit 21.1 (subsidiaries list); "25" in the accession = filed 2025.

**Q: So the JSON is the metadata downloaded and doc is the other one?**
A: Nearly. Two JSONs: the filings list (downloaded, not saved) and the metadata file (written by
our script, not downloaded). The doc is the 10-K itself.

**Q: SUBMISSIONS_URL is the thing thrown away?**
A: The URL is the address; the *data* fetched from it is used then discarded.

**Q: Apple's list of filings is available as a JSON file?**
A: Yes, at a fixed address for every company (an API). Same info as the EDGAR website, in a
format code can read.

**Q: Why do I need $env:SEC_USER_AGENT?**
A: The SEC requires every automated request to identify who's asking (name + email); without it you
get 403. It's an env var, not hard-coded, because (1) my email stays out of the public repo and
(2) config ≠ code: each person/environment sets its own value. `$env:` lasts only for the current
terminal session → moves to a .env file in Phase 3.

**Q: (check) If EDGAR listed filings oldest-first, which 10-K would we get?**
A: The oldest. The function returns the first match. Spotting hidden assumptions is part of code review.

**Q: (check) What goes wrong without metadata, or re-downloading every run?**
A: Without provenance, citations can't point back to the exact filing. Re-downloading wastes
time, risks SEC rate limits, and breaks reproducibility (if "latest" changes, evals silently run
on different data).

## Gotchas
- Always check the CIK, not the name.
- Click the document whose Type is `10-K`, not EX-21/EX-31.
- No spaces in URLs.
- Set `$env:SEC_USER_AGENT` in every new terminal (until .env in Phase 3).

## Commands I used
uv add httpx
$env:SEC_USER_AGENT = "Taha Rizvi <email>"
uv run python scripts/download_10k.py --ticker AAPL --cik 320193
Get-Content data\raw\AAPL\AAPL_10-K_2026-09-26.json

## Interview version
"Ingestion is a script, not a manual download: it hits the official EDGAR submissions API,
respects SEC fair-access rules, is idempotent, and writes a provenance sidecar (source URL,
accession number, dates) for every document. That metadata is what later makes citations
traceable back to an exact filing."

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
