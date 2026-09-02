#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
rsync -a "$SRC/platform/schema/" "$DST/platform/schema/"
rsync -a "$SRC/command-center/schema/" "$DST/command-center/schema/"
rsync -a "$SRC/command-center/p2-wave/probes/CC-0019/" "$DST/command-center/p2-wave/probes/CC-0019/"
rsync -a "$SRC/command-center/p2-wave/probes/WFA-0148/probe2_plant.py" "$DST/command-center/p2-wave/probes/WFA-0148/probe2_plant.py"
rsync -a "$SRC/command-center/p2-wave/probes/CNF-0072/" "$DST/command-center/p2-wave/probes/CNF-0072/"
rsync -a "$SRC/command-center/p2-wave/probes/AUD-0059/" "$DST/command-center/p2-wave/probes/AUD-0059/"
rsync -a "$SRC/command-center/audit/AUD-0059-hook-firing-evidence.json" "$DST/command-center/audit/AUD-0059-hook-firing-evidence.json"
rsync -a "$SRC/command-center/receipts/CC-0019.json" "$DST/command-center/receipts/CC-0019.json"
rsync -a "$SRC/command-center/confirmation/CNF-0072-option-id-namespaces.json" "$DST/command-center/confirmation/CNF-0072-option-id-namespaces.json"
rsync -a "$SRC/command-center/p2-wave/seed-stage/rewrite_schema_file_ids.py" "$DST/command-center/p2-wave/seed-stage/rewrite_schema_file_ids.py"
export AST_INTEGRATE_ROOT="$DST"
python3 "$DST/command-center/p2-wave/seed-stage/rewrite_schema_file_ids.py"
echo SCHEMA-RSYNC-REWRITE-OK
