#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
mkdir -p "$DST"
rsync -a --checksum \
  --exclude .git \
  --exclude node_modules \
  --exclude __pycache__ \
  --exclude command-center/p2-wave/ovh-monitor \
  "$SRC/" "$DST/"
echo DELTA-RSYNC-OK
du -sh "$DST"
