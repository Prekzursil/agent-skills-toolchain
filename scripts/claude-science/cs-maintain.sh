#!/bin/bash
# cs-maintain — weekly offline SQLite maintenance for the Claude Science daemon.
# Stops the daemon, backs up FIRST, integrity-checks, checkpoints/vacuums/optimizes,
# then restarts pinned (--no-auto-update). NOTE: ANALYZE/VACUUM/checkpoint here are tiny-DB
# hygiene, NOT the wedge fix -- the ~164s wedge is host-RAM freezing WSL, not DB cost (2026-07-07 audit).
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
# Config seam. Fail LOUD if a partial deploy dropped it: without cs-lib.sh the helpers below
# are undefined and every $CS_* is empty, which would silently target the wrong paths.
_cs_lib="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cs-lib.sh"
[ -r "$_cs_lib" ] || { echo "!!! cs-lib.sh missing beside $0 - re-run install.ps1 (it deploys cs-lib.sh + cs.conf)" >&2; exit 1; }
# shellcheck source=cs-lib.sh
. "$_cs_lib"
DD="$(cs_data_dir)"
# cs_find_db picks the NEWEST-mtime DB. `find | head -1` across the two org dirs could
# maintain one org's DB while cs-backup snapshotted the other -- both steps "succeed".
DB=$(cs_find_db)

echo "[maintain] stopping daemon (graceful, then scoped kill)"
pid=$(claude-science status 2>/dev/null | grep -oE '"pid":[[:space:]]*[0-9]+' | grep -oE '[0-9]+' | head -1)
timeout 12 claude-science stop >/dev/null 2>&1 || true
sleep 1
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
  echo "[maintain] graceful stop timed out; TERM->KILL pid $pid (+ children)"
  pkill -TERM -P "$pid" 2>/dev/null; kill -TERM "$pid" 2>/dev/null; sleep 2
  kill -9 "$pid" 2>/dev/null || true
fi
# last resort, PRECISELY scoped to the detached daemon child only (NOT a broad `pkill -9 -f claude-science`,
# which SIGKILLs any editor/grep/log-tail on the path and can corrupt the DB mid-write)
pkill -9 -f 'claude-science serve .*--_daemon-child' 2>/dev/null || true
sleep 1
rm -f "$DD/daemon.sock" "$DD/operon.lock" 2>/dev/null || true

echo "[maintain] backup first"
if command -v cs-backup >/dev/null 2>&1; then cs-backup; else bash "$(dirname "$0")/cs-backup.sh"; fi

DEST="$CS_BACKUP_ROOT"
if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "!!! [maintain] sqlite3 NOT FOUND on PATH — SKIPPING the entire DB maintenance block"
  echo "!!! [maintain] (integrity_check + checkpoint + VACUUM silently no-op without it; install: sudo apt-get install -y sqlite3)"
elif [ -z "$DB" ]; then
  echo "!!! [maintain] operon-cli.db not found under $DD/orgs — SKIPPING DB maintenance"
else
  echo "[maintain] integrity_check: $(sqlite3 "$DB" 'PRAGMA integrity_check;' | head -1)"
  echo "[maintain] journal_mode: $(sqlite3 "$DB" 'PRAGMA journal_mode;')"
  # Refuse to VACUUM (rewrites the whole DB in place) with no rollback point: assert cs-backup
  # just wrote a fresh operon-*.db (< 10 min old) to $DEST. If not, WARN loudly and SKIP VACUUM.
  # -size +0c: a fresh but ZERO-byte snapshot is not a usable rollback point -> require non-empty
  fresh_bk=$(find "$DEST" -maxdepth 1 -name 'operon-*.db' -mmin -10 -size +0c 2>/dev/null | head -1)
  if [ -z "$fresh_bk" ]; then
    echo "!!! [maintain] NO fresh backup (operon-*.db < 10 min old) in $DEST"
    echo "!!! [maintain] SKIPPING destructive VACUUM (no rollback point) — checkpoint+optimize only"
    sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE); PRAGMA optimize;" && echo "[maintain] checkpoint+optimize done (VACUUM SKIPPED)"
  else
    echo "[maintain] fresh backup verified: $fresh_bk"
    sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE); VACUUM; ANALYZE; PRAGMA optimize;" && echo "[maintain] checkpoint+vacuum+analyze+optimize done"
  fi
fi

# server-log retention: drop server-*.log older than 14 days (keep ~/.claude-science/logs bounded)
find "$DD/logs" -maxdepth 1 -name 'server-*.log' -mtime +14 -delete 2>/dev/null || true
echo "[maintain] pruned server logs older than 14 days"

echo "[maintain] restart (pinned, no auto-update)"
read -ra cs_extra <<<"$(cat "$HOME/.cs-serve-extra" 2>/dev/null || true)"
claude-science serve --no-browser --detached --no-auto-update "${cs_extra[@]}" 2>&1 | tail -3
sleep 6
claude-science status 2>/dev/null | grep -E '"running"|"pid"' || echo "[maintain] WARN: not running after restart"
