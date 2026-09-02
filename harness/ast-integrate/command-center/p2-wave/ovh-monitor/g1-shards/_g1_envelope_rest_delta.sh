#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
mkdir -p "$DST"
copy_one() {
  local rel="$1"
  local dest_dir
  dest_dir="$DST/$(dirname "$rel")"
  mkdir -p "$dest_dir"
  rsync -a --checksum "$SRC/$rel" "$dest_dir/"
}
copy_one command-center/phase3/A4
copy_one command-center/phase3/A8
copy_one command-center/control-plane/A4
copy_one command-center/confirmation/CNF-0063-source-corroboration.json
copy_one command-center/schema/confirmation-receipt.schema.json
copy_one command-center/schema/discrepancy-record.schema.json
copy_one command-center/schema/validate_confirmation_receipt.py
copy_one command-center/p2-wave/probes/ARC-0024
copy_one command-center/p2-wave/probes/ARC-0058
copy_one command-center/p2-wave/probes/CNF-0001
copy_one command-center/p2-wave/probes/CNF-0063
copy_one command-center/p2-wave/_measure_one_delivered.py
copy_one command-center/p2-wave/seed-stage
echo RSYNC-DELTA-OK
