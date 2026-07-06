#!/usr/bin/env bash
# One-shot setup for ColdEmails.
#
#   ./setup.sh                 # interactive: prompts for HUNTER_API_KEY if unset
#   ./setup.sh <hunter_key>    # non-interactive: writes the key into .env
#
# Creates .venv, installs deps (+ Streamlit, pytest), seeds .env from
# .env.example, and runs the offline test suite. Safe to re-run.

set -euo pipefail
cd "$(dirname "$0")"

echo "==> Python venv"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt streamlit pytest
.venv/bin/pip install -q -e . 2>/dev/null || true   # `coldemails` CLI (best-effort)

echo "==> .env"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    created .env from .env.example"
fi

# Fill HUNTER_API_KEY from the argument, or prompt if empty and interactive.
key="${1:-}"
current="$(grep -E '^HUNTER_API_KEY=' .env | cut -d= -f2- || true)"
if [ -z "$current" ]; then
  if [ -z "$key" ] && [ -t 0 ]; then
    read -r -p "    Paste your Hunter.io API key (enter to skip): " key
  fi
  if [ -n "$key" ]; then
    tmp="$(mktemp)"
    sed "s|^HUNTER_API_KEY=.*|HUNTER_API_KEY=$key|" .env > "$tmp" && mv "$tmp" .env
    echo "    HUNTER_API_KEY saved to .env"
  else
    echo "    HUNTER_API_KEY still empty — add it to .env before finding prospects"
  fi
else
  echo "    HUNTER_API_KEY already set"
fi

echo "==> Tests (offline)"
.venv/bin/python -m pytest -q

cat <<'DONE'

Setup complete. Next:
  .venv/bin/streamlit run app.py       # web UI at http://localhost:8501
  .venv/bin/python -m coldemails.cli campaigns
Or, inside Claude Code, just type: /coldemails
DONE
