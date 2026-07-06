---
description: Boot up the ColdEmails project — first-run setup if needed, then live UI on localhost
---

Get the ColdEmails project running end-to-end. Work from the repo root.

## 1. First-run setup (only if needed)
- If `.venv/` is missing or `.env` is missing, run `bash setup.sh` (it creates
  the venv, installs deps, seeds `.env` from `.env.example`, and runs tests).
- Check `HUNTER_API_KEY` in `.env`. If it's empty and I didn't provide one in
  $ARGUMENTS, ask me to paste my Hunter.io API key, then write it into `.env`
  (never commit `.env`; it is gitignored).
- If anything else looks broken, consult `HANDOFF.md` — it documents the
  environment gotchas (root-owned package dir, auto-push watcher, claude_cli
  model pinning) before debugging from scratch.

## 2. Verify
- Run `.venv/bin/python -m pytest -q` and confirm the suite passes.
- Report which optional keys are set (`ANTHROPIC_API_KEY`, `SERPER_API_KEY`,
  `SENDER_EMAIL`/Gmail) and what each unlocks.

## 3. Launch
- Start the UI in the background:
  `.venv/bin/streamlit run app.py --server.headless true`
- Confirm it's serving (e.g. `curl -s -o /dev/null -w '%{http_code}' http://localhost:8501`)
  and tell me it's live at **http://localhost:8501**.

## 4. Summary
Finish with a short status: setup done/skipped, tests, configured keys,
UI URL, and the suggested next steps from HANDOFF.md.

If $ARGUMENTS contains a task (e.g. "preview jobs at Stripe for ML Engineer"),
do steps 1–2, skip the UI launch, and run the matching CLI command instead:
`.venv/bin/python -m coldemails.cli preview --campaign ... --company ... --role ...`
(always `preview`, never `send`, unless I explicitly say send).
