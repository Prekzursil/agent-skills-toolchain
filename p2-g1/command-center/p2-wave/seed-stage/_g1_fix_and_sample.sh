#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
export AST_INTEGRATE_ROOT="$SRC"
cd "$SRC"
python3 -u command-center/p2-wave/seed-stage/_write_fanin.py
SITE=$(python3 -c 'import site; print(site.getusersitepackages())')
mkdir -p "$SITE"
cp command-center/p2-wave/seed-stage/p2_jsonschema_hook.py "$SITE/p2_jsonschema_hook.py"
cp command-center/p2-wave/seed-stage/sitecustomize_jsonschema.py "$SITE/sitecustomize.py"
printf 'import p2_jsonschema_hook\n' > "$SITE/p2g1.pth"
# drop bytecode of old sitecustomize
rm -f "$SITE"/__pycache__/sitecustomize*.pyc "$SITE"/__pycache__/p2_jsonschema_hook*.pyc
python3 -c 'import importlib, jsonschema, p2_jsonschema_hook; print("Draft7", type(jsonschema.Draft7Validator), jsonschema.Draft7Validator.__name__)'
python3 -u command-center/p2-wave/seed-stage/_diag_g1_samples.py
