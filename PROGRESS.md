# fin-rag — Progress Log

## Phase 1 · Step 1 — Minimal environment ✅ (2026-11-19)
**Done**
- uv 0.11.25, Python 3.12.13, project `fin-rag` at D:\Projects\RAGsolution (src layout, `uv init --package`)
- .gitignore (venv, .env, data/, models, vector DB files, caches), .gitattributes (LF normalisation)
- Git identity: GitHub noreply email (account rizvi1111); first commit pushed to github.com/rizvi1111/fin-rag (main)

**Decisions**
- uv over pip/poetry/conda: lockfile + Python version management in one fast tool
- src layout: tests run against the installed package, catches import bugs early
- `* text=auto eol=lf`: consistent line endings for Windows dev + Linux CI/Docker
- uv cache on D: (same drive as projects) so uv can hardlink packages into .venv

**Environment notes**
- PowerShell 5.1 (no `&&`; avoid `>` for writing files, since it writes UTF-16)
- uv cache on D: via %APPDATA%\uv\uv.toml (`cache-dir`), since the env var approach didn't stick
- OS build 26100 → likely Windows 11, confirm with `winver` and update constraints doc

## Phase 1 · Step 2 — Data (small) ✅ (2026-11-19)
**Done**
- scripts/download_10k.py: EDGAR submissions API → latest 10-K (inline XBRL HTML) + JSON provenance sidecar
- First doc: Apple 10-K, FY ending 2026-09-26, filed 2026-11-03 (1.7 MB) → data/raw/AAPL/ (gitignored)
- First dependency: httpx

**Decisions**
- HTML over PDF: official EDGAR format, tables preserved as <table> for better parsing later
- Script over manual download: reproducible, idempotent
- SEC_USER_AGENT via env var: keeps email out of repo; config not code (→ .env in Phase 3)
- Filing is post-LLM-cutoff → answers must come from retrieval, not model memory



**Open questions**
- None