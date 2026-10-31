#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
mkdir -p "$DST"

rsync -a --delete \
  --exclude __pycache__ \
  --exclude '*.pyc' \
  --exclude mcp \
  "$SRC/tools/" "$DST/tools/"

while IFS= read -r uid; do
  [ -z "$uid" ] && continue
  if [ -d "$SRC/command-center/p2-wave/probes/$uid" ]; then
    mkdir -p "$DST/command-center/p2-wave/probes/$uid"
    rsync -a --exclude __pycache__ --exclude deps \
      "$SRC/command-center/p2-wave/probes/$uid/" \
      "$DST/command-center/p2-wave/probes/$uid/"
  fi
done < "$SRC/command-center/p2-wave/ovh-monitor/g1-shards/shard-07.txt"

for d in command-center/receipts command-center/adversarial command-center/audit \
         command-center/wfa command-center/research command-center/schema \
         command-center/p2-wave/seed-stage command-center/confirmation \
         command-center/design; do
  if [ -d "$SRC/$d" ]; then
    mkdir -p "$DST/$d"
    rsync -a --exclude __pycache__ "$SRC/$d/" "$DST/$d/"
  fi
done

rsync -a "$SRC/command-center/p2-wave/_measure_one_delivered.py" \
  "$DST/command-center/p2-wave/_measure_one_delivered.py"
echo RSYNC-SHARD07-OK
du -sh "$DST"
