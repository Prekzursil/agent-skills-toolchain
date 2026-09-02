#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
mkdir -p "$DST"
# Full tree (same flags as seed-stage/_g1_rsync.sh) plus a fast delta of this
# shard's units so G-1 can measure even if the full pass is still running.
paths=(
  command-center/phase3/A4
  command-center/phase3/A8
  command-center/control-plane/A4
  command-center/confirmation/CNF-0063-source-corroboration.json
  command-center/schema/confirmation-receipt.schema.json
  command-center/schema/discrepancy-record.schema.json
  command-center/schema/validate_confirmation_receipt.py
  command-center/p2-wave/probes/ARC-0024
  command-center/p2-wave/probes/ARC-0058
  command-center/p2-wave/probes/CNF-0001
  command-center/p2-wave/probes/CNF-0063
  command-center/p2-wave/_measure_one_delivered.py
  command-center/p2-wave/seed-stage
)
for p in "${paths[@]}"; do
  mkdir -p "$DST/$(dirname "$p")"
  rsync -a --checksum "$SRC/$p" "$DST/$(dirname "$p")/"
done
echo RSYNC-DELTA-OK
# Full checksum rsync (excludes ovh-monitor as in _g1_rsync.sh).
rsync -a --checksum \
  --exclude .git \
  --exclude node_modules \
  --exclude __pycache__ \
  --exclude command-center/p2-wave/ovh-monitor \
  "$SRC/" "$DST/"
echo RSYNC-OK
du -sh "$DST"
