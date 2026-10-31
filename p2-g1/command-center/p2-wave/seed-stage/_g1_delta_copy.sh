#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
mkdir -p "$DST"
# Copy only the trees this shard edited. Avoid a full checksum walk.
rsync -a --exclude __pycache__ "$SRC/tools/" "$DST/tools/"
rsync -a --exclude __pycache__ "$SRC/hooks/_shared/" "$DST/hooks/_shared/"
rsync -a --exclude __pycache__ "$SRC/platform/schema/" "$DST/platform/schema/"
rsync -a --exclude __pycache__ "$SRC/command-center/receipts/" "$DST/command-center/receipts/"
rsync -a --exclude __pycache__ "$SRC/command-center/phase3/" "$DST/command-center/phase3/"
rsync -a --exclude __pycache__ "$SRC/command-center/p2-wave/probes/" "$DST/command-center/p2-wave/probes/"
rsync -a "$SRC/command-center/receipt_writer.py" "$DST/command-center/receipt_writer.py"
rsync -a "$SRC/command-center/p2-wave/_measure_one_delivered.py" "$DST/command-center/p2-wave/_measure_one_delivered.py"
echo DELTA-COPY-OK
du -sh "$DST"
