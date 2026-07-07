# Host ColdEmails on Render with background bulk sends

> **Status: DRAFT pending Ultraplan refinement.** A refined version of this plan
> exists in a Claude Code cloud session; when it is teleported back, update this
> file to match. Until then, this draft is the authoritative local copy.

## Context

The Streamlit front end currently runs only on the user's machine. The goal is an
*optional* hosted mode on Render so a user can open a URL anytime and trigger bulk
outreach runs — without breaking or complicating local use. Four things block naive
hosting today: (1) the default `claude_cli` draft mode needs a local Claude Code
login, (2) Gmail OAuth consent opens a local browser, (3) SQLite must live on a
persistent disk, (4) the app has no auth — a public URL could send email from the
owner's Gmail. Additionally, a 25-prospect send takes ~19 min in the browser tab
today; hosted use needs background jobs.

Everything is additive and gated by env vars: with nothing set, local behavior is
unchanged.

## Changes

### 1. Optional password gate (`app.py`)
- New env `APP_PASSWORD`. If unset → no gate (local unchanged). If set → a minimal
  login screen (password input, compared via `hmac.compare_digest`, stored flag in
  `st.session_state`) before `main()` renders.
- Sidebar shows a "hosted mode" note when gated.

### 2. Gmail token from env (`coldemails/gmail.py`)
- New env `GMAIL_TOKEN_JSON`: if set and the token file is missing, write its
  contents to `GMAIL_TOKEN_FILE` before the OAuth check in `_get_service()`.
  Flow: user runs `coldemails test-send` locally once (browser consent, creates
  `token.json`), then pastes the file contents into a Render secret. Refresh
  writes back to the file on the disk mount, so it survives restarts.
- If neither token nor credentials exist, raise a clear error naming both options.

### 3. Background job runner (new flat module `coldemails/jobs.py`)
- `jobs` table added to `store.py` SCHEMA: `id, campaign, kind(preview|send),
  state(running|done|failed), found/rendered/sent/skipped/failed counts, log TEXT,
  error, created_at, updated_at`. Store methods: `create_job`, `update_job`,
  `finish_job`, `get_job`, `latest_job(campaign)`.
- `jobs.start_run(...)`: spawns a `threading.Thread` that opens its **own Store**
  (sqlite connections are thread-bound), runs `Engine.run(...)`, streams log lines
  and counts into the jobs row, marks done/failed. Returns job id.
- `app.py`: **Send** (after the existing confirm dialog) starts a job instead of
  running inline, stores the job id in session state, and shows a job-status panel
  (counts, tail of log, state badge) with a refresh control (`st.fragment
  (run_every=...)` while running). Revisiting the page shows `latest_job` for the
  campaign, so a closed tab loses nothing. **Preview stays synchronous** (fast,
  interactive).
- CLI unchanged (synchronous is right there).

### 4. Draft-mode awareness in hosted env (`app.py`)
- If `shutil.which("claude")` is None, default the segmented control to
  "Claude API" (or "Template" when no `ANTHROPIC_API_KEY`) and caption why the
  CLI mode is unavailable.

### 5. Render deployment files
- `render.yaml` blueprint: docker web service from the repo, disk (1 GB) mounted
  at `/data`, `COLDEMAILS_DB=/data/coldemails.db`, `GMAIL_TOKEN_FILE=/data/token.json`,
  env vars declared (`APP_PASSWORD`, `HUNTER_API_KEY`, `ANTHROPIC_API_KEY`,
  `SERPER_API_KEY`, `SENDER_NAME`, `SENDER_EMAIL`, `GMAIL_TOKEN_JSON` — all
  `sync: false` secrets).
- Dockerfile: also `COPY .streamlit/ .streamlit/` (theme), keep the rest.
- Note: Render's free tier sleeps when idle → "anytime" needs the ~$7/mo starter
  instance; free works for trying it out.

### 6. Docs
- README: new "Deploy to Render" section (mint token locally → `backup.sh` →
  blueprint deploy → paste secrets), and the hosted-mode caveats (API-key
  drafting, shared credentials, password gate).
- HANDOFF.md: state + gotchas (thread-per-job + per-thread Store, token-from-env).

## Files touched
`app.py`, `coldemails/gmail.py`, `coldemails/store.py`, `coldemails/jobs.py` (new),
`render.yaml` (new), `Dockerfile`, `README.md`, `HANDOFF.md`, tests below.

## Reuse
- `Engine.run` unchanged — jobs wrap it via its existing `log` callback.
- `Store` already context-managed; jobs thread opens its own instance.
- Existing confirm dialog, badges, and metrics UI are reused for job status.

## Verification
1. `pytest` — new tests: jobs table CRUD; `start_run` end-to-end with stubbed
   source + template renderer (poll until `done`, assert counts/log persisted);
   `GMAIL_TOKEN_JSON` materializes the file; password gate helper (correct/wrong
   password).
2. Headless `AppTest`: gated render when `APP_PASSWORD` set; ungated when not.
3. `docker build` + `docker run --env-file .env -e APP_PASSWORD=x -v $(pwd)/data:/data`
   → browser check: login gate, preview run, background send job.
4. Playwright screenshot of the gate + job panel (same harness as the redesign).
5. Actual Render deploy is the user's click (blueprint from repo) — document,
   verify manually afterwards.

## Out of scope (explicitly)
Multi-tenant per-user keys/Gmail; job cancellation; email reply tracking.
