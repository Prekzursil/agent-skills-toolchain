#!/bin/bash
set -euo pipefail
SITE=$(python3 -c 'import site; print(site.getusersitepackages())')
mkdir -p "$SITE"
cp /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/seed-stage/sitecustomize_jsonschema.py "$SITE/sitecustomize.py"
python3 -c 'import sitecustomize, jsonschema; print("SITECUST-OK")'
mkdir -p "$HOME/p2-g1"
rsync -a --delete --exclude .git --exclude node_modules --exclude command-center/p2-wave/ovh-monitor /mnt/c/Users/Prekzursil/source/ast-integrate/ "$HOME/p2-g1/"
echo RSYNC-OK
du -sh "$HOME/p2-g1"
cd "$HOME/p2-g1"
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
export G1_WORKERS=24
export PYTHONPATH="$HOME/p2-g1:$HOME/p2-g1/platform/lib"
exec python3 -u command-center/p2-wave/seed-stage/g1_remeasure_all.py
