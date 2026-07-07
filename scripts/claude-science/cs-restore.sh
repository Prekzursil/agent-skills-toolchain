#!/bin/bash
# cs-restore <timestamp|latest> [--dry-run] - roll back to a cs-backup snapshot. The missing inverse
# of cs-backup.sh (a backup you can't restore is false safety). Matches cs-backup's format exactly:
#   DB      -> /mnt/d/Backups/claude-science/operon-<TS>.db
#   key     -> /mnt/d/Backups/claude-science-keys/encryption.key  (stored separately)
# Stops the daemon, clears locks, keeps a pre-restore safety copy, restores the DB (+ drops the
# stale WAL/SHM so it opens clean), re-places the encryption key, restarts pinned, verifies HTTP 401
# (auth gate = alive). --dry-run prints the plan and changes nothing. Fails LOUD if the backup or D:
# is missing.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
DD="$HOME/.claude-science"
DEST="/mnt/d/Backups/claude-science"
KEYDEST="/mnt/d/Backups/claude-science-keys"

# --- args: <ts|latest> in any order with --dry-run/-n ---
DRYRUN=0
sel=""
for a in "$@"; do
  case "$a" in
    --dry-run | -n) DRYRUN=1 ;;
    -*) echo "!!! unknown flag '$a' (usage: cs-restore <ts|latest> [--dry-run])" >&2; exit 2 ;;
    *) sel="$a" ;;
  esac
done
sel="${sel:-latest}"

# --- resolve the snapshot (fail LOUD if D: unmounted or no matching backup) ---
[ -d "$DEST" ] || { echo "!!! backup dir $DEST not found (is D: mounted?)" >&2; exit 1; }
if [ "$sel" = latest ]; then
  db=$(find "$DEST" -maxdepth 1 -name 'operon-*.db' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
else
  db="$DEST/operon-$sel.db"
fi
if [ -z "$db" ] || [ ! -f "$db" ]; then
  echo "!!! no backup db for '$sel' (${db:-none})" >&2
  echo "available snapshots:"
  find "$DEST" -maxdepth 1 -name 'operon-*.db' -printf '%f\n' 2>/dev/null | sort || echo "  (none)"
  exit 1
fi
ts=$(basename "$db" | sed -E 's/^operon-(.*)\.db$/\1/')

live=$(find "$DD/orgs" -name operon-cli.db 2>/dev/null | head -1)
[ -n "$live" ] || { echo "!!! live operon-cli.db not found under $DD/orgs" >&2; exit 1; }

# --- dry-run: show the plan, touch nothing ---
if [ "$DRYRUN" = 1 ]; then
  echo "cs-restore DRY-RUN: snapshot $ts  ->  $live"
  echo "  1) stop daemon + clear daemon.sock/operon.lock/stale sandbox sockets"
  echo "  2) safety-copy current DB -> $live.pre-restore"
  echo "  3) copy $db -> $live  (+ drop $live-wal / $live-shm)"
  if [ -f "$KEYDEST/encryption.key" ]; then echo "  4) re-place encryption.key from $KEYDEST"; else echo "  4) (no $KEYDEST/encryption.key to re-place)"; fi
  echo "  5) restart daemon (pinned) + verify HTTP 401"
  exit 0
fi

echo "cs-restore: snapshot $ts  ->  $live"
echo "1) stop daemon + clear locks"
timeout 12 claude-science stop >/dev/null 2>&1 || true
sleep 1
pkill -9 -f 'claude-science serve .*--_daemon-child' 2>/dev/null || true
sleep 1
rm -f "$DD/daemon.sock" "$DD/operon.lock" 2>/dev/null
rm -rf "$DD"/sbx-bind-src/sock-* 2>/dev/null

echo "2) safety copy of the current DB (rollback point)"
cp -f "$live" "$live.pre-restore" 2>/dev/null && echo "   kept $live.pre-restore"

echo "3) restore DB (drop stale WAL/SHM so it opens clean)"
rm -f "$live-wal" "$live-shm" 2>/dev/null
cp -f "$db" "$live"
if [ -f "$KEYDEST/encryption.key" ]; then
  cp -f "$KEYDEST/encryption.key" "$DD/encryption.key" && echo "   re-placed encryption.key"
fi

echo "4) restart (pinned) + verify"
CS_EXTRA=$(cat "$HOME/.cs-serve-extra" 2>/dev/null || true)
read -r -a CS_EXTRA_ARR <<<"$CS_EXTRA"
claude-science serve --no-browser --detached --no-auto-update "${CS_EXTRA_ARR[@]}" 2>&1 | tail -3
sleep 6

verify_up() {
  # prefer a real HTTP 401 (auth gate = alive); fall back to the daemon status flag
  if command -v curl >/dev/null 2>&1; then
    code=$(curl -s -o /dev/null -m 8 -w '%{http_code}' http://127.0.0.1:8000/ 2>/dev/null || echo 000)
    case "$code" in 401 | 200) return 0 ;; esac
  fi
  claude-science status 2>/dev/null | grep -q '"running": true'
}

if verify_up; then
  echo "cs-restore: OK - running on snapshot $ts"
else
  echo "!!! restart FAILED after restore - $live.pre-restore preserved; 'cs fix' or restore another snapshot" >&2
  exit 1
fi
