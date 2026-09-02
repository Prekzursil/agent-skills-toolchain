#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
rm -f "$DST/tools/workflow.py" "$DST/tools/synthesis.py"
rsync -a "$SRC/tools/council/" "$DST/tools/council/"
rsync -a "$SRC/tools/workflow/" "$DST/tools/workflow/"
rsync -a "$SRC/tools/synthesis/" "$DST/tools/synthesis/"
rsync -a "$SRC/tools/detector_control/" "$DST/tools/detector_control/"
rsync -a "$SRC/tools/agentspec/agentspec/" "$DST/tools/agentspec/agentspec/"
rsync -a "$SRC/tools/plugin/" "$DST/tools/plugin/"
rsync -a "$SRC/tools/marketplace/" "$DST/tools/marketplace/"
rsync -a "$SRC/tools/router/" "$DST/tools/router/"
rsync -a "$SRC/tools/lib/" "$DST/tools/lib/"
rsync -a "$SRC/tools/command-center/" "$DST/tools/command-center/"
rsync -a "$SRC/command-center/adapters/" "$DST/command-center/adapters/"
rsync -a "$SRC/command-center/p2-wave/probes/CNF-0151/" "$DST/command-center/p2-wave/probes/CNF-0151/"
echo RSYNC-B-OK
