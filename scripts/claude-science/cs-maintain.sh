#!/bin/bash
# cs-maintain — weekly offline SQLite maintenance for the Claude Science daemon.
# Stops the daemon, backs up FIRST, integrity-checks, checkpoints/vacuums/optimizes,
# then restarts pinned (--no-auto-update). Reduces the lock-contention wedge frequency.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
DD="$HOME/.claude-science"
DB=$(find "$DD/orgs" -name operon-cli.db 2>/dev/null | head -1)

echo "[maintain] stopping daemon"
claude-science stop 2>/dev/null || true
pkill -9 -f claude-science 2>/dev/null || true
sleep 2
rm -f "$DD/daemon.sock" "$DD/operon.lock" 2>/dev/null || true

echo "[maintain] backup first"
if command -v cs-backup >/dev/null 2>&1; then cs-backup; else bash "$(dirname "$0")/cs-backup.sh"; fi

if [ -n "$DB" ]; then
  echo "[maintain] integrity_check: $(sqlite3 "$DB" 'PRAGMA integrity_check;' | head -1)"
  echo "[maintain] journal_mode before: $(sqlite3 "$DB" 'PRAGMA journal_mode;')"
  sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE); VACUUM; ANALYZE; PRAGMA optimize;" && echo "[maintain] checkpoint+vacuum+optimize done"
fi

echo "[maintain] restart (pinned, no auto-update)"
CS_EXTRA=$(cat "$HOME/.cs-serve-extra" 2>/dev/null || true)
claude-science serve --no-browser --detached --no-auto-update $CS_EXTRA 2>&1 | tail -3
sleep 6
claude-science status 2>/dev/null | grep -E '"running"|"pid"' || echo "[maintain] WARN: not running after restart"
