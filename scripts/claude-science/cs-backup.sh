#!/bin/bash
# cs-backup — consistent snapshot of ~/.claude-science to D:, with the encryption key
# stored SEPARATELY so a leaked data backup is inert. Safe to run while the daemon is up
# (uses SQLite's online .backup API). Keeps the last 7 of each.
set -uo pipefail
# Config seam. Fail LOUD if a partial deploy dropped it: without cs-lib.sh the helpers below
# are undefined and every $CS_* is empty, which would silently target the wrong paths.
_cs_lib="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cs-lib.sh"
[ -r "$_cs_lib" ] || { echo "!!! cs-lib.sh missing beside $0 - re-run install.ps1 (it deploys cs-lib.sh + cs.conf)" >&2; exit 1; }
# shellcheck source=cs-lib.sh
. "$_cs_lib"
DD="$(cs_data_dir)"
DEST="$CS_BACKUP_ROOT"
KEYDEST="$CS_BACKUP_KEY_ROOT"
TS=$(date +%Y%m%d-%H%M%S)

# GUARD: `set -uo pipefail` has NO `-e`, so a failed mkdir / unwritable dest would silently
# continue and the caller would never notice the backup didn't land. Verify D: is mounted and
# DEST is writable; otherwise bail LOUD. (This backup is the rollback point cs-maintain checks for.)
# The mount to verify is DERIVED from the configured root (/mnt/d/Backups/... -> /mnt/d) rather
# than hardcoded, so pointing CS_BACKUP_ROOT at another drive still gets a real mount check.
CS_MNT=$(printf '%s' "$DEST" | sed -n 's#^\(/mnt/[^/]*\).*#\1#p')
if [ -n "$CS_MNT" ] && command -v mountpoint >/dev/null 2>&1 && ! mountpoint -q "$CS_MNT" 2>/dev/null; then
  echo "!!! backup dest not writable (drive mounted?) — $CS_MNT is not a mount point" >&2
  exit 1
fi
if ! mkdir -p "$DEST" "$KEYDEST" 2>/dev/null || [ ! -w "$DEST" ]; then
  echo "!!! backup dest not writable (D: mounted?) — cannot create/write $DEST" >&2
  exit 1
fi
chmod 700 "$KEYDEST" 2>/dev/null || true

# cs_find_db picks the NEWEST-mtime DB, not `find | head -1`. There are two org dirs on this box
# and find order is filesystem order, so the old form could snapshot one org's DB while cs-doctor
# pronounced the OTHER one healthy -- both rows green, the wrong file backed up.
DB=$(cs_find_db)
if [ -n "$DB" ]; then
  if sqlite3 "$DB" ".timeout 10000" ".backup '$DEST/operon-$TS.db'"; then
    echo "[backup] db snapshot: operon-$TS.db ($(stat -c%s "$DEST/operon-$TS.db") bytes) <- $DB"
    # VERIFY THE SNAPSHOT OPENS. A backup that cannot be restored is false safety, and a truncated
    # or half-written .backup exits 0 often enough that "the command succeeded" is not evidence.
    if ! sqlite3 -readonly "file:$DEST/operon-$TS.db?mode=ro" "PRAGMA integrity_check;" 2>&1 | grep -qx 'ok'; then
      echo "!!! [backup] snapshot operon-$TS.db FAILED integrity_check - treat it as unusable" >&2
      exit 1
    fi
    echo "[backup] snapshot verified: integrity_check=ok"
  else
    echo "!!! [backup] sqlite .backup FAILED for $DB" >&2
    exit 1
  fi
else
  echo "!!! [backup] operon-cli.db not found under $DD/orgs - NOTHING WAS BACKED UP" >&2
  exit 1
fi

# tar the data dir WITHOUT secrets or re-downloadable bulk (conda/runtime)
tar -czf "$DEST/data-$TS.tar.gz" -C "$HOME" \
  --exclude='.claude-science/encryption.key' \
  --exclude='.claude-science/.oauth-tokens' \
  --exclude='.claude-science/conda' \
  --exclude='.claude-science/runtime' \
  --exclude='.claude-science/sbx-bind-src' \
  .claude-science 2>/dev/null && echo "[backup] data tar: data-$TS.tar.gz ($(stat -c%s "$DEST/data-$TS.tar.gz") bytes)"

# secrets to a SEPARATE dir (RT7: never co-locate key with the ciphertext it protects)
cp -a "$DD/encryption.key" "$KEYDEST/encryption.key" 2>/dev/null && echo "[backup] key -> $KEYDEST (separate)"
[ -d "$DD/.oauth-tokens" ] && cp -a "$DD/.oauth-tokens" "$KEYDEST/" 2>/dev/null && echo "[backup] oauth-tokens -> $KEYDEST"

# retention: keep last 7
find "$DEST" -maxdepth 1 -name 'operon-*.db' 2>/dev/null | sort -r | tail -n +8 | while IFS= read -r f; do rm -f "$f"; done
find "$DEST" -maxdepth 1 -name 'data-*.tar.gz' 2>/dev/null | sort -r | tail -n +8 | while IFS= read -r f; do rm -f "$f"; done
echo "[backup] done -> $DEST  |  free: $(df -h "$DEST" | awk 'NR==2{print $4}')"
