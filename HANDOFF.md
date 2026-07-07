# Handoff — ColdEmails (for Fable 5)

Context for the next agent picking up this repo. Read this, then `README.md` for
usage. This file is about *state, decisions, and gotchas* — not usage.

## What this project is

Multi-purpose cold-outreach engine. Given search criteria it finds people, gets
their emails (Hunter.io), researches background, drafts a personalized email
(Claude), and sends via Gmail — throttled, de-duplicated, tracked in SQLite.
One engine + swappable interfaces + per-campaign config. Built as a Python CLI
with a Streamlit web UI on top.

## Current status: working v1.1 (2026-07-05 enhancement pass)

- 7 campaigns: `jobs`, `fundraising`, `b2b`, `pr`, `podcast`, `partnerships`,
  `recruiting` (`coldemails/campaigns.py`)
- CLI: `preview`, `send`, `status`, `campaigns`, `export` (CSV), `discover-firms`
- Streamlit UI: `app.py` (`streamlit run app.py`, port 8501) — redesigned per
  `design_handoff_1b_streamlit/` (Direction 1b): scoped CSS with the handoff's
  design tokens, campaign card grid, `st.pills` firm chips, `st.segmented_control`
  draft mode, `st.dialog` send-confirm with checkbox gate, status badges, empty
  state, dark-mode toggle, CSV download. Needs Streamlit ≥1.40 (keyed containers,
  pills); `.venv` has 1.58.
- 48 offline tests pass, 1 skipped (`pytest`) — network + LLM stubbed
- **Verified live** (v1): real Hunter.io lookup + claude_cli drafting, dry-run.
- New in v1.1:
  - `company.resolve` uses Clearbit's free autocomplete API (keyless) with a
    smarter slug fallback (strips legal suffixes). Disable network lookup with
    `COLDEMAILS_NO_NETWORK_RESOLVE=1` (conftest sets it for tests).
  - AI-written subject lines: both Claude renderers ask for `Subject: ...` +
    blank line + body; `personalize._parse_email` splits, falls back to
    `fallback_subject` if the model omits it.
  - Expanded VC catalog (~85 firms) in `firmfinder.py`.
  - `Dockerfile` + `.dockerignore` for the Streamlit UI (claude_cli mode won't
    work in Docker — use the API-key mode there).
  - `.venv/` created at repo root (gitignored) with deps + pytest.
  - Attachments (2026-07-06): `Message.attachments` (file paths), `gmail.build_mime`
    (multipart when present), `Engine.run(attachments=...)` validates paths and
    falls back to an optional campaign-level `attachments` default; CLI `--attach`
    (repeatable); UI file-uploader in Step 03 (temp-dir persisted), listed in the
    send-confirm dialog and dry-run output.

## Architecture (all flat modules — see "gotchas" for why)

```
coldemails/
  engine.py       orchestrates find→enrich→personalize→send+track; dedup; throttle
  models.py       Person / Message / Criteria; Person.dedup_key(campaign)
  store.py        SQLite: prospects, status, background, dedup (idempotent runs)
  sources.py      ProspectSource: HunterSource + HunterFirmsSource (multi-domain)
  enrich.py       Enricher: WebEnricher (fetch org pages) + SearchEnricher (Serper/DDG)
  personalize.py  Personalizer: ClaudeCLIRenderer, ClaudeRenderer, TemplateRenderer
  gmail.py        Sender: GmailSender (OAuth, throttled) + ConsoleSender (dry-run)
  company.py      company name → domain (naive slugify — see next steps)
  campaigns.py    campaign configs (dict); firmfinder catalog is separate
  firmfinder.py   VC/angel firm discovery: curated US/EU/Asia + Serper search
  config.py       env() + load_dotenv
app.py            Streamlit UI (read-only sidebar; config comes from .env)
tests/            40 tests
```

Adding a campaign = a dict entry in `campaigns.py` (+ maybe a template/enricher).
No engine changes needed — that's the core design.

## Personalization / draft modes (important)

- `claude_cli` (**default**) — shells out to local `claude -p --model ...`. Uses
  the machine's Claude Code login, **no ANTHROPIC_API_KEY**. This is what the
  user wants (they run from Claude Code).
- `claude` — Anthropic SDK, needs `ANTHROPIC_API_KEY`.
- `template` — deterministic, no AI.

## Secrets / state

- `.env` exists and is **gitignored**. It holds a real, user-provided
  `HUNTER_API_KEY`. Do NOT commit `.env`, and do not quote key material
  (even prefixes) in committed files.
- No Anthropic key set (not needed with `claude_cli`).
- Gmail: SENDER_EMAIL/SENDER_NAME set in `.env`, Google client libs installed,
  `coldemails test-send` command ready — **waiting only on the user's
  `credentials.json`** (OAuth Desktop client from Google Cloud) + one browser
  consent. Real sending still untested until then.

## Environment gotchas (these bit me; they'll bite you)

1. **`coldemails/` dir is root-owned.** The Write tool can create *files* there
   but `mkdir` of subdirs fails (EACCES). That's why the package is **flat**
   (`sources.py`, not `sources/`). Keep it flat. `tests/` and repo root are
   user-owned and fine.
2. **Auto-push watcher.** Something (running as root) auto-commits every file
   change as `auto-push: <file>` and pushes to `origin/main`. So the history
   fills with granular commits. The user periodically asks to **squash**:
   `git reset --soft 265debf && git commit ... && git push --force-with-lease`.
3. **Root-owned git objects.** The watcher's commits leave some
   `.git/objects/<xx>/` dirs root-owned, so your commit can fail with
   "insufficient permission for adding an object". Fix: retry the commit — a new
   timestamp = new object hash = usually a writable prefix. A small retry loop works.
4. **`claude -p` needs `--model`.** Without it the CLI inherits this session's
   model (`claude-3-5-sonnet-v2`) which is unavailable and errors. `personalize.py`
   pins `COLDEMAILS_CLAUDE_CLI_MODEL` or `CLAUDE_MODEL` (Haiku 4.5).
5. **DuckDuckGo blocks bots** (202 anomaly page). The keyless search backend
   won't return results in practice — use `SERPER_API_KEY`. Code falls back cleanly.
6. **venv location:** tests/app were run with an interpreter at
   `/private/tmp/.../scratchpad/venv/bin/python`. The user should make their own
   venv (`python -m venv .venv`); don't hardcode the scratchpad path.

## Docs (read in this order on cold start)

1. `CLAUDE.md` — standing orders: commands, don'ts, done-criteria.
2. This file — state, decisions, environment gotchas.
3. `docs/BUILD_PLAN.md` — staged remaining roadmap with per-step verification.
4. `docs/hosting-plan.md` — approved Render-hosting design (Stage 2 detail);
   header notes it may be superseded by a refined Ultraplan.

## Backups

`./backup.sh` copies the unrecoverable gitignored state (`.env`, `coldemails.db`,
Gmail OAuth files once present, + a prospects.csv export) to
`~/Backups/coldemails/<timestamp>/`, owner-only permissions. First backup taken
2026-07-06. Re-run after changing keys or real sends.

## Git

- Clean history target: two commits — `265debf Initial commit` + one squashed
  feature commit. Currently the README rewrite is **uncommitted** in the working
  tree (or freshly auto-pushed as granular commits — check `git log`).
- `origin`: https://github.com/deka1105/ColdEmails.git, branch `main`.

## Suggested next steps (not yet done)

1. **Configure Gmail + do one real send** to the user's own address. This is the
   only integration never run live. Needs their OAuth `credentials.json` + consent.
2. **Live-verify the new pieces**: Clearbit resolution and the AI subject-line
   parsing (offline-tested only; a `coldemails preview` run covers both).
3. **Follow-up sequences** — track a `sent_at` and support a polite bump email.
4. **Correct the VC catalog tags** in `firmfinder.py` (still approximate).

Done since v1: company resolver (Clearbit), 3 new campaigns, AI subjects,
expanded catalog, CSV export, Dockerfile.

## How to verify quickly

```bash
pytest                                   # 40 pass, offline
coldemails campaigns                     # lists 4 campaigns
coldemails discover-firms --sector climate --location EU
coldemails preview --campaign jobs --company Stripe --role "ML Engineer" \
    --location Berlin --limit 2          # live Hunter + claude_cli draft, dry-run
```
