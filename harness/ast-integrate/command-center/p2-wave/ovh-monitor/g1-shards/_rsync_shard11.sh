#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
mkdir -p "$DST"
# Fast trees probes actually import. No --checksum (9p is too slow).
rsync -a --exclude __pycache__ --exclude '*.pyc' \
  "$SRC/command-center/p2-wave/_measure_one_delivered.py" \
  "$DST/command-center/p2-wave/_measure_one_delivered.py"
rsync -a --exclude __pycache__ --exclude '*.pyc' \
  "$SRC/command-center/p2-wave/seed-stage/" \
  "$DST/command-center/p2-wave/seed-stage/"
rsync -a "$SRC/command-center/WORK-UNIT-CATALOG.json" "$DST/command-center/WORK-UNIT-CATALOG.json"
for tree in \
  command-center/p2-wave/probes \
  command-center/schema \
  command-center/receipts \
  command-center/adversarial \
  command-center/audit \
  command-center/phase3 \
  command-center/phase4 \
  command-center/conformance \
  tools \
  plugin \
  marketplace \
  platform \
  workflow_foundry \
  router \
  layout
do
  if [ -e "$SRC/$tree" ]; then
    mkdir -p "$DST/$(dirname "$tree")"
    rsync -a --exclude __pycache__ --exclude '*.pyc' --exclude .git \
      "$SRC/$tree/" "$DST/$tree/" 2>/dev/null || rsync -a "$SRC/$tree" "$DST/$tree"
  fi
done
# Per-unit probe dirs (idempotent overlay)
while IFS= read -r uid; do
  [ -z "$uid" ] && continue
  srcp="$SRC/command-center/p2-wave/probes/$uid"
  dstp="$DST/command-center/p2-wave/probes/$uid"
  if [ -d "$srcp" ]; then
    mkdir -p "$dstp"
    rsync -a --exclude __pycache__ --exclude '*.pyc' "$srcp/" "$dstp/"
  fi
done < /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-11.txt
echo RSYNC-SHARD11-OK
du -sh "$DST"
