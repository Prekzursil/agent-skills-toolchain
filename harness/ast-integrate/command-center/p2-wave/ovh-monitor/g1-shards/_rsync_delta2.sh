#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
rsync -a "$SRC/command-center/p2-wave/probes/CNF-0183/isolate.py" "$DST/command-center/p2-wave/probes/CNF-0183/isolate.py"
rsync -a "$SRC/tools/plugin/exit_codes.py" "$DST/tools/plugin/exit_codes.py"
echo DELTA2-OK
