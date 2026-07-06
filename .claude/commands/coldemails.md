---
description: Boot up the ColdEmails project — load context, verify setup, start the UI
---

Initiate the ColdEmails project:

1. Read `HANDOFF.md` for current state, decisions, and environment gotchas
   (root-owned package dir, auto-push watcher, claude_cli model pinning).
2. Verify the environment:
   - `.venv` exists (if not: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest streamlit`)
   - Run `.venv/bin/python -m pytest -q` and confirm the suite passes.
   - Check which keys are set in `.env` (HUNTER_API_KEY required; report the rest).
3. Start the Streamlit UI in the background:
   `.venv/bin/streamlit run app.py --server.headless true`
   and tell me it's at http://localhost:8501.
4. Give me a short status summary: tests, configured keys, running services,
   and the suggested next steps from HANDOFF.md.

If I passed an argument ($ARGUMENTS), treat it as a task to do instead of
step 3 (e.g. "preview jobs at Stripe" → run the matching
`.venv/bin/python -m coldemails.cli preview ...` command).
