#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
FAILS=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/class-other.fail-ids.txt
mkdir -p "$DST"
bash "$SRC/command-center/p2-wave/seed-stage/_g1_rsync.sh"
export AST_INTEGRATE_ROOT="$DST"
cd "$DST"
python3 -u "$DST/command-center/p2-wave/seed-stage/rewrite_schema_file_ids.py"
python3 -u "$DST/command-center/p2-wave/seed-stage/_refresh_g1_manifests.py"
export PYTHONPATH="$DST:$DST/platform/lib:$DST/tools:$DST/tools/agentspec:$DST/command-center/p2-wave/seed-stage"
export G1_WORKERS="${G1_WORKERS:-6}"
export G1_FAILS_FILE="$FAILS"
python3 -u "$DST/command-center/p2-wave/seed-stage/_g1_measure_assigned.py"
