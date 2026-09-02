#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
rsync -a --checksum \
  "$SRC/tools/" "$DST/tools/"
rsync -a --checksum \
  "$SRC/command-center/lib/" "$DST/command-center/lib/"
rsync -a --checksum \
  "$SRC/command-center/bench/" "$DST/command-center/bench/"
rsync -a --checksum \
  "$SRC/command-center/p2-wave/_measure_one_delivered.py" \
  "$DST/command-center/p2-wave/_measure_one_delivered.py"
echo RSYNC-SHARD13-OK
