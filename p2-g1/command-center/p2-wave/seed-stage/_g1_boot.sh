#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
mkdir -p "$DST"
rsync -a --delete \
  --exclude .git \
  --exclude node_modules \
  --exclude __pycache__ \
  --exclude command-center/p2-wave/ovh-monitor \
  "$SRC/" "$DST/"
echo RSYNC-OK
du -sh "$DST"
SITE=$(python3 -c 'import site; print(site.getusersitepackages())')
mkdir -p "$SITE"
cp "$DST/command-center/p2-wave/seed-stage/p2_jsonschema_hook.py" "$SITE/p2_jsonschema_hook.py"
cp "$DST/command-center/p2-wave/seed-stage/sitecustomize_jsonschema.py" "$SITE/sitecustomize.py"
printf 'import p2_jsonschema_hook\n' > "$SITE/p2g1.pth"
python3 -c 'import p2_jsonschema_hook, jsonschema; print("HOOK-OK")'
cd "$DST"
export AST_INTEGRATE_ROOT="$DST"
export PYTHONPATH="$DST:$DST/platform/lib:$DST/tools/agentspec:$DST/command-center/p2-wave/seed-stage"
export G1_WORKERS="${G1_WORKERS:-16}"
python3 -u "$DST/command-center/p2-wave/seed-stage/restore_missing_probes.py"
python3 -u "$DST/command-center/p2-wave/seed-stage/fix_g1_receipts.py"
exec python3 -u "$DST/command-center/p2-wave/seed-stage/g1_remeasure_all.py"
