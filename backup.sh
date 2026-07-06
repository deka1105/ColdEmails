#!/usr/bin/env bash
# Back up the gitignored local state that can't be recovered from GitHub:
# .env (API keys), coldemails.db (send/dedup history), and Gmail OAuth files.
#
#   ./backup.sh            # -> ~/Backups/coldemails/<timestamp>/
#   ./backup.sh /some/dir  # -> custom destination

set -euo pipefail
cd "$(dirname "$0")"

dest="${1:-$HOME/Backups/coldemails}/$(date +%Y-%m-%d_%H%M%S)"
mkdir -p "$dest"

copied=0
for f in .env coldemails.db credentials.json token.json; do
  if [ -f "$f" ]; then
    cp "$f" "$dest/"
    echo "  saved $f"
    copied=$((copied + 1))
  fi
done

# Human-readable export of prospects alongside the raw DB, when possible.
if [ -f coldemails.db ] && [ -x .venv/bin/python ]; then
  .venv/bin/python -m coldemails.cli export --out "$dest/prospects.csv" 2>/dev/null \
    && echo "  saved prospects.csv" || true
fi

chmod -R go-rwx "$dest"   # backups hold API keys — owner-only
echo "Backed up $copied file(s) to $dest"
