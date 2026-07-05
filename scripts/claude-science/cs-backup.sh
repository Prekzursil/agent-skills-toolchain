#!/bin/bash
# cs-backup — consistent snapshot of ~/.claude-science to D:, with the encryption key
# stored SEPARATELY so a leaked data backup is inert. Safe to run while the daemon is up
# (uses SQLite's online .backup API). Keeps the last 7 of each.
set -uo pipefail
DD="$HOME/.claude-science"
DEST="/mnt/d/Backups/claude-science"
KEYDEST="/mnt/d/Backups/claude-science-keys"
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p "$DEST" "$KEYDEST"
chmod 700 "$KEYDEST" 2>/dev/null || true

DB=$(find "$DD/orgs" -name operon-cli.db 2>/dev/null | head -1)
if [ -n "$DB" ]; then
  sqlite3 "$DB" ".timeout 10000" ".backup '$DEST/operon-$TS.db'" && echo "[backup] db snapshot: operon-$TS.db ($(stat -c%s "$DEST/operon-$TS.db") bytes)"
else
  echo "[backup] WARN: operon-cli.db not found"
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
ls -1t "$DEST"/operon-*.db 2>/dev/null | tail -n +8 | xargs -r rm -f
ls -1t "$DEST"/data-*.tar.gz 2>/dev/null | tail -n +8 | xargs -r rm -f
echo "[backup] done -> $DEST  |  free: $(df -h "$DEST" | awk 'NR==2{print $4}')"
