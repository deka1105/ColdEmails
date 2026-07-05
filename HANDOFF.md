# Handoff — ColdEmails (for Fable 5)

Context for the next agent picking up this repo. Read this, then `README.md` for
usage. This file is about *state, decisions, and gotchas* — not usage.

## What this project is

Multi-purpose cold-outreach engine. Given search criteria it finds people, gets
their emails (Hunter.io), researches background, drafts a personalized email
(Claude), and sends via Gmail — throttled, de-duplicated, tracked in SQLite.
One engine + swappable interfaces + per-campaign config. Built as a Python CLI
with a Streamlit web UI on top.

## Current status: working v1

- 4 campaigns: `jobs`, `fundraising`, `b2b`, `pr` (`coldemails/campaigns.py`)
- CLI: `preview`, `send`, `status`, `campaigns`, `discover-firms` (`cli.py`)
- Streamlit UI: `app.py` (`streamlit run app.py`, port 8501)
- 40 offline tests pass (`pytest`) — network + LLM stubbed
- **Verified live**: real Hunter.io lookup (Stripe → 2 real prospects+emails) +
  drafting via the Claude Code CLI, dry-run. End-to-end works.

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

- `.env` exists and is **gitignored**. It holds a real `HUNTER_API_KEY`
  (`dcc020c7...` — user-provided). Do NOT commit `.env`.
- No Anthropic key set (not needed with `claude_cli`).
- Gmail not yet configured → real sending untested.

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

## Git

- Clean history target: two commits — `265debf Initial commit` + one squashed
  feature commit. Currently the README rewrite is **uncommitted** in the working
  tree (or freshly auto-pushed as granular commits — check `git log`).
- `origin`: https://github.com/deka1105/ColdEmails.git, branch `main`.

## Suggested next steps (not yet done)

1. **Configure Gmail + do one real send** to the user's own address. This is the
   only integration never run live. Needs their OAuth `credentials.json` + consent.
2. **Improve `company.resolve`** — currently just slugifies to `.com`; wrong for
   many companies. Consider a real resolver (Clearbit autocomplete / search).
3. **More campaigns** (podcast, partnerships, recruiting) — cheap config adds.
4. **Expand / correct the VC catalog** in `firmfinder.py` (tags are approximate).
5. **Deploy option** — Dockerfile for hosting the Streamlit app (note: `claude_cli`
   mode won't work off a machine without Claude Code; fall back to API key there).

## How to verify quickly

```bash
pytest                                   # 40 pass, offline
coldemails campaigns                     # lists 4 campaigns
coldemails discover-firms --sector climate --location EU
coldemails preview --campaign jobs --company Stripe --role "ML Engineer" \
    --location Berlin --limit 2          # live Hunter + claude_cli draft, dry-run
```
