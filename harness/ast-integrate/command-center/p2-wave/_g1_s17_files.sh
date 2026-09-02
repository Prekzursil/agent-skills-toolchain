#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST=/home/prekzursil/p2-g1
rsync -a "$SRC/tools/artifact_cache/store.py" "$DST/tools/artifact_cache/store.py"
rsync -a "$SRC/command-center/lib/evidence_snapshot/targets.py" "$DST/command-center/lib/evidence_snapshot/targets.py"
rsync -a "$SRC/command-center/lib/evidence_snapshot/__init__.py" "$DST/command-center/lib/evidence_snapshot/__init__.py"
rsync -a "$SRC/command-center/p2-wave/probes/ADV-0047/lifecycle.py" "$DST/command-center/p2-wave/probes/ADV-0047/lifecycle.py"
echo FILES-OK
