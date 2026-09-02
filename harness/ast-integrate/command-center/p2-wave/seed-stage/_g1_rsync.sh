#!/usr/bin/env bash
# Sync the state of record -> the execution mirror, then probes run in the mirror.
#   owner's box : SRC=/mnt/c/.../ast-integrate (Windows tree)   DST=~/p2-g1 (WSL)
#   cloud Linux : SRC=<this repo's harness/ast-integrate>       DST=${G1_MIRROR:-~/p2-g1}
# No --delete (persistent-mirror semantics, as on the owner's box): probe side effects
# from earlier runs stay in the mirror and never enter git. ovh-monitor (ledgers) is
# excluded -- it is read/written in SRC directly by the tools (_g1_paths.MON).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d /mnt/c/Users/Prekzursil/source/ast-integrate ]; then
  SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
else
  SRC="$(cd "$HERE/../../.." && pwd)"
fi
DST="${G1_MIRROR:-$HOME/p2-g1}"
mkdir -p "$DST"
rsync -a ${G1_RSYNC_CHECKSUM:+--checksum} \
  --exclude .git \
  --exclude node_modules \
  --exclude __pycache__ \
  --exclude command-center/p2-wave/ovh-monitor \
  "$SRC/" "$DST/"
echo "RSYNC-OK $SRC -> $DST"
du -sh "$DST" 2>/dev/null | cut -f1
