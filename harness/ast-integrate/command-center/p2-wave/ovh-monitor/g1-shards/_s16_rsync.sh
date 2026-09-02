#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
mkdir -p "$DST/tools" "$DST/command-center/fusion" "$DST/command-center/lib" \
  "$DST/command-center/p2-wave/probes" "$DST/command-center/receipts"
rsync -a --exclude .git --exclude node_modules --exclude __pycache__ \
  --exclude command-center/p2-wave/ovh-monitor \
  "$SRC/tools/" "$DST/tools/"
rsync -a --exclude __pycache__ "$SRC/command-center/fusion/" "$DST/command-center/fusion/"
rsync -a --exclude __pycache__ "$SRC/command-center/lib/" "$DST/command-center/lib/"
rsync -a --exclude __pycache__ "$SRC/command-center/p2-wave/probes/" "$DST/command-center/p2-wave/probes/"
rsync -a "$SRC/command-center/p2-wave/_measure_one_delivered.py" \
  "$DST/command-center/p2-wave/_measure_one_delivered.py"
rsync -a --exclude __pycache__ "$SRC/command-center/receipts/" "$DST/command-center/receipts/"
# Also copy fusion/lib parents in case first clone was sparse.
test -f "$DST/command-center/fusion/admission_gate.py"
test -f "$DST/command-center/lib/windows_safe_path.py"
echo RSYNC-OK
du -sh "$DST"
