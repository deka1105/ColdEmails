# ColdEmails

Personal cold-outreach engine: pick a campaign, enter criteria → finds prospects
(Hunter.io) → researches them → drafts personalized email (Claude) → sends via
Gmail — throttled, de-duplicated, tracked in SQLite. Python CLI + Streamlit UI.
Single-user tool for legitimate 1:1 outreach; keep volume low.

## Stack

- Python 3.10+ (venv at `.venv/`, Streamlit 1.58), SQLite, no framework.
- Flat package `coldemails/` (no subpackages — see Don'ts).
- UI: `app.py`, one Streamlit file, custom CSS per `design_handoff_1b_streamlit/`.

## Commands

```bash
./setup.sh [HUNTER_KEY]                  # venv + deps + .env + tests (idempotent)
.venv/bin/python -m pytest -q            # offline test suite — must stay green
.venv/bin/streamlit run app.py           # UI at http://localhost:8501
.venv/bin/python -m coldemails.cli campaigns|preview|send|status|export|discover-firms|test-send
./backup.sh                              # snapshot .env + DB to ~/Backups/coldemails/
```

`preview` is always a dry run. `send` sends real email — never run it without
explicit user instruction.

## Where things live

- `coldemails/engine.py` — pipeline orchestration; `campaigns.py` — campaign
  configs (adding a use case = one dict entry, no engine changes);
  `sources.py` (Hunter), `enrich.py` (web/search research), `personalize.py`
  (claude_cli / claude API / template renderers), `gmail.py` (send + MIME),
  `store.py` (SQLite), `firmfinder.py` (VC catalog), `company.py` (name→domain).
- `HANDOFF.md` — current state, decisions, environment gotchas. **Read it first.**
- `docs/hosting-plan.md` — approved plan for Render hosting + background jobs.
- `docs/BUILD_PLAN.md` — staged roadmap with per-stage verification.
- `tests/` — offline; network and LLM always stubbed.

## Don'ts

- **Never commit `.env`, `credentials.json`, `token.json`**, or quote key
  material (even prefixes) in committed files.
- **Don't create subdirectories inside `coldemails/`** — the dir is root-owned
  on the primary machine; mkdir fails. Keep the package flat.
- **Don't run `coldemails send`** (or the UI Send) unless the user explicitly
  asks; default to `preview`.
- **Don't call `claude -p` without `--model`** — it inherits an unavailable
  session model. `personalize.py` pins it; keep that.
- **Don't add network calls to tests** — suite must pass offline with no keys
  (`COLDEMAILS_NO_NETWORK_RESOLVE=1` is set in `tests/conftest.py`).

## Environment quirks (bite every session — details in HANDOFF.md)

- An auto-push watcher (root) commits every file change as `auto-push: <file>`
  and pushes to origin/main. Don't fight it; user occasionally squashes history.
- Root-owned `.git/objects` prefixes can fail commits — retrying usually works.
- DuckDuckGo blocks bot search; use `SERPER_API_KEY` for live search features.

## Before saying "done"

1. `.venv/bin/python -m pytest -q` passes (55+ tests).
2. If `app.py` changed: headless check
   (`streamlit.testing.v1.AppTest.from_file("app.py")` runs with no exceptions),
   and for visual changes, screenshot via Playwright and actually look at it.
3. If CLI changed: run the touched subcommand once for real (dry-run flags only).
4. Update HANDOFF.md when state, decisions, or gotchas changed.
