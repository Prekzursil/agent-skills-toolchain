#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
mkdir -p "$DST"
rsync -a \
  --exclude .git \
  --exclude node_modules \
  --exclude __pycache__ \
  --exclude command-center/p2-wave/ovh-monitor \
  "$SRC/" "$DST/"
export AST_INTEGRATE_ROOT="$DST"
cd "$DST"
python3 -u "$DST/command-center/p2-wave/seed-stage/_write_fanin.py"
python3 -u "$DST/command-center/p2-wave/seed-stage/rewrite_schema_file_ids.py"
python3 -u "$DST/command-center/p2-wave/seed-stage/fast_fill_receipts.py"
python3 -u "$DST/command-center/p2-wave/seed-stage/restore_missing_probes.py" || true
SITE=$(python3 -c 'import site; print(site.getusersitepackages())')
mkdir -p "$SITE"
cp "$DST/command-center/p2-wave/seed-stage/p2_jsonschema_hook.py" "$SITE/p2_jsonschema_hook.py"
cp "$DST/command-center/p2-wave/seed-stage/sitecustomize.py" "$SITE/sitecustomize.py"
python3 -c 'import p2_jsonschema_hook, jsonschema; print("HOOK", p2_jsonschema_hook.HOOK_VERSION, type(jsonschema.Draft7Validator))'
export PYTHONPATH="$DST:$DST/platform/lib:$DST/tools/agentspec:$DST/command-center/p2-wave/seed-stage"
export G1_WORKERS="${G1_WORKERS:-16}"
# heartbeat still lands on the Windows ovh-monitor path
python3 -u "$DST/command-center/p2-wave/seed-stage/g1_remeasure_all.py"
