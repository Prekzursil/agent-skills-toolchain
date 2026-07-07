#!/bin/bash
# cs-restore <timestamp|latest> — roll back to a cs-backup snapshot. The missing inverse of
# cs-backup.sh (a backup you can't restore is false safety). Matches cs-backup's format exactly:
#   DB      -> /mnt/d/Backups/claude-science/operon-<TS>.db
#   key     -> /mnt/d/Backups/claude-science-keys/encryption.key  (stored separately)
# Stops the daemon, clears locks, keeps a pre-restore safety copy, restores the DB (+ drops the
# stale WAL/SHM so it opens clean), re-places the encryption key, restarts pinned, verifies.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
DD="$HOME/.claude-science"
DEST="/mnt/d/Backups/claude-science"
KEYDEST="/mnt/d/Backups/claude-science-keys"
sel="${1:-latest}"

[ -d "$DEST" ] || { echo "!!! backup dir $DEST not found (is D: mounted?)"; exit 1; }
if [ "$sel" = latest ]; then db=$(ls -1t "$DEST"/operon-*.db 2>/dev/null | head -1); else db="$DEST/operon-$sel.db"; fi
[ -f "$db" ] || { echo "!!! no backup db for '$sel' ($db)"; echo "available snapshots:"; ls -1 "$DEST"/operon-*.db 2>/dev/null | sed 's#.*/##' || echo "  (none)"; exit 1; }
ts=$(basename "$db" | sed -E 's/^operon-(.*)\.db$/\1/')

live=$(find "$DD/orgs" -name operon-cli.db 2>/dev/null | head -1)
[ -n "$live" ] || { echo "!!! live operon-cli.db not found under $DD/orgs"; exit 1; }

echo "cs-restore: snapshot $ts  ->  $live"
echo "1) stop daemon + clear locks"
timeout 12 claude-science stop >/dev/null 2>&1 || true; sleep 1
pkill -9 -f 'claude-science serve .*--_daemon-child' 2>/dev/null || true; sleep 1
rm -f "$DD/daemon.sock" "$DD/operon.lock" 2>/dev/null; rm -rf "$DD"/sbx-bind-src/sock-* 2>/dev/null

echo "2) safety copy of the current DB (rollback point)"
cp -f "$live" "$live.pre-restore" 2>/dev/null && echo "   kept $live.pre-restore"

echo "3) restore DB (drop stale WAL/SHM so it opens clean)"
rm -f "$live-wal" "$live-shm" 2>/dev/null
cp -f "$db" "$live"
if [ -f "$KEYDEST/encryption.key" ]; then cp -f "$KEYDEST/encryption.key" "$DD/encryption.key" && echo "   re-placed encryption.key"; fi

echo "4) restart (pinned) + verify"
CS_EXTRA=$(cat "$HOME/.cs-serve-extra" 2>/dev/null || true)
claude-science serve --no-browser --detached --no-auto-update $CS_EXTRA 2>&1 | tail -3
sleep 6
if claude-science status 2>/dev/null | grep -q '"running": true'; then
  echo "cs-restore: OK — running on snapshot $ts"
else
  echo "!!! restart FAILED after restore — $live.pre-restore preserved; 'cs fix' or restore another snapshot"
  exit 1
fi
