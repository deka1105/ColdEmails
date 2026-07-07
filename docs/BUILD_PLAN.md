# ColdEmails — Build Plan (remaining roadmap)

## Handoff block (paste-first for a fresh session)

ColdEmails is a working single-user cold-outreach engine (Hunter.io prospects →
Claude-drafted emails → Gmail sends, SQLite-tracked). Repo root has `CLAUDE.md`
(standing orders — read it), `HANDOFF.md` (state + environment gotchas), and
`docs/hosting-plan.md` (approved design for Stage 2). The engine, CLI, Streamlit
UI, attachments, and 56 offline tests are **done and verified**; Gmail has
**never sent a real email** (blocked on the user's `credentials.json`). Execute
the stages below in order — each is independent, sized for one session, and ends
with something you can see working. Verify with the exact commands given; never
run a real `send` without the user's explicit go-ahead.

**Approach chosen:** keep the single-user, env-var-gated architecture and layer
hosted mode + lifecycle features onto the existing engine, rather than
(rejected a) rebuilding as a Next.js + API backend — far more work for no
single-user benefit — or (rejected b) a multi-tenant SaaS with per-user keys —
explicitly out of scope; the user wants optional hosting, not a product.
Decisions inherit; don't relitigate.

---

## Stage 1 — Gmail live verification

**Visible endpoint:** a real test email (with attachment) in the user's inbox.

- **Goal:** prove OAuth consent, token caching, MIME assembly, and sending live.
- **Where:** no code — `credentials.json` (user supplies, repo root), then run.
- **Verify:**
  `.venv/bin/python -m coldemails.cli test-send --attach README.md`
  → browser consent → "Sent. Check …" → user confirms receipt; `token.json`
  exists; second run sends with no browser. Then `./backup.sh` (captures token).
- **Fence:** do not touch campaign sending, do not email anyone but the user,
  do not commit either JSON file.
- **Blocked on user:** Google Cloud OAuth Desktop client (steps in README
  "Sending email"). Nothing to build meanwhile — skip to Stage 3 if blocked.

## Stage 2 — Render hosting with background jobs

**Visible endpoint:** password-gated app at a live `*.onrender.com` URL; a bulk
preview keeps running after the tab closes and shows progress on revisit.

Full design is in `docs/hosting-plan.md` — follow it. Step order:
1. Password gate in `app.py` (`APP_PASSWORD` env; unset = unchanged local).
   *Verify:* AppTest with/without env var; screenshot the gate.
2. `GMAIL_TOKEN_JSON` env → token file materialization in `gmail.py`.
   *Verify:* new unit test (env set + file absent → file written, used).
3. `jobs` table + methods in `store.py`; thread runner `coldemails/jobs.py`
   (thread opens its own Store — sqlite connections are thread-bound).
   *Verify:* pytest job lifecycle test (stubbed source, poll to `done`).
4. Wire UI Send → job + status panel (`st.fragment(run_every=...)`).
   *Verify:* AppTest + manual browser run of a 3-prospect preview job.
5. `render.yaml` + Dockerfile tweak (`COPY .streamlit/`).
   *Verify:* `docker build` + `docker run -e APP_PASSWORD=x --env-file .env
   -v $(pwd)/data:/data -p 8501:8501 coldemails` → gate, preview, job panel.
6. User deploys blueprint on Render, pastes secrets. *Verify:* live URL.
- **Fence:** no multi-tenant auth, no job cancellation, no Postgres migration.
  Local no-env behavior must stay byte-identical (existing 56 tests still pass).

## Stage 3 — Follow-up sequences

**Visible endpoint:** `coldemails followups --campaign jobs` lists who's due a
bump; `--send` sends one polite follow-up per stale prospect, exactly once.

- **Goal:** re-contact prospects sent >N days ago (default 7), once.
- **Where:** `store.py` (add `sent_at REAL`, `followup_sent_at REAL` — additive
  `ALTER TABLE`-style migration guarded by `PRAGMA table_info`), `engine.py`
  (small `run_followups`), `campaigns.py` (per-campaign `followup_prompt`),
  `cli.py` (`followups` subcommand), UI panel later (optional).
- **Verify:** pytest — freeze time, mark sent, assert due-listing and
  send-once; CLI dry-run prints the drafts.
- **Fence:** no reply detection (needs Gmail read scope — explicitly out),
  max one follow-up per prospect, dry-run default.

## Stage 4 — Safety + polish

**Visible endpoint:** a suppressed address is visibly skipped in a preview run;
an oversized attachment fails fast with a clear error.

- **Suppression list:** `suppressions` table + `coldemails suppress <email>` /
  `unsuppress` / list; engine checks before render *and* before send.
  *Verify:* pytest + CLI round-trip.
- **Attachment size guard:** reject runs where total attachments > 20 MB
  (Gmail limit ~25 MB with encoding overhead) in `Engine.run` validation.
  *Verify:* pytest with a tmp big file.
- **Attachments on result cards:** show names in UI results + history.
  *Verify:* AppTest render.
- **Fence:** no unsubscribe-link injection into bodies (1:1 outreach, not
  bulk marketing), no HTML email.

---

## Risks & tripwires

1. **Google OAuth app in "testing" mode expires tokens after 7 days.**
   *Tripwire:* Stage 1's second `test-send` re-prompts for consent days later.
   *Fallback:* publish the OAuth app (still unverified is fine for one user) or
   re-consent weekly; document whichever in HANDOFF.md.
2. **Streamlit threads + Render restarts can orphan `running` jobs.**
   *Tripwire:* a job stuck `running` with a stale `updated_at` (>10 min).
   *Fallback:* on app start, mark stale running jobs `failed («interrupted»)` —
   build this into Stage 2 step 3, it's two lines.
3. **Render free tier sleeps; "anytime" quietly becomes "after a cold start".**
   *Tripwire:* first request after idle takes ~1 min. *Fallback:* starter
   instance (~$7/mo) — a user decision, note it at deploy time.
4. **Clearbit autocomplete (company→domain) could be sunset by HubSpot.**
   *Tripwire:* `test_company_resolve_clearbit`-style live check starts failing /
   resolver logs fallbacks. *Fallback:* already built — slug fallback keeps
   working; swap in a search-API resolver if quality drops.

## Progress log (update as stages complete)

- [ ] Stage 1 — Gmail live verification *(blocked on user's credentials.json)*
- [ ] Stage 2 — Render hosting + background jobs *(design approved; may be
      superseded by refined Ultraplan — check docs/hosting-plan.md header)*
- [ ] Stage 3 — Follow-up sequences
- [ ] Stage 4 — Suppression + attachment guard + polish
