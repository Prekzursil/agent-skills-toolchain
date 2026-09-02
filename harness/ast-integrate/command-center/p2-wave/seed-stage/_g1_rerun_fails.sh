#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
mkdir -p "$DST"
rsync -a "$SRC/command-center/p2-wave/probes/" "$DST/command-center/p2-wave/probes/"
rsync -a "$SRC/command-center/p2-wave/seed-stage/" "$DST/command-center/p2-wave/seed-stage/"
rsync -a "$SRC/command-center/p2-wave/_measure_one_delivered.py" "$DST/command-center/p2-wave/_measure_one_delivered.py"
rsync -a "$SRC/command-center/p2-wave/ovh-monitor/g1-local-full.jsonl" "$DST/command-center/p2-wave/ovh-monitor/g1-local-full.jsonl" || true
mkdir -p "$DST/command-center/p2-wave/ovh-monitor"
# keep Windows jsonl as input
export AST_INTEGRATE_ROOT="$DST"
export G1_WORKERS="${G1_WORKERS:-16}"
export PYTHONPATH="$DST:$DST/platform/lib:$DST/tools/agentspec:$DST/command-center/p2-wave/seed-stage"
cd "$DST"
python3 -u "$DST/command-center/p2-wave/seed-stage/_write_fanin.py"
exec python3 -u "$DST/command-center/p2-wave/seed-stage/g1_remeasure_fails.py"
