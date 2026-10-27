#!/usr/bin/env bash
set -euo pipefail
ROOT=/mnt/c/Users/Prekzursil/source/ast-integrate
export AST_INTEGRATE_ROOT="$ROOT"
cd "$ROOT"
SITE=$(python3 -c 'import site; print(site.getusersitepackages())')
mkdir -p "$SITE"
cp "$ROOT/command-center/p2-wave/seed-stage/sitecustomize_jsonschema.py" "$SITE/sitecustomize.py"
python3 -c 'import sitecustomize, jsonschema; print("SITECUST-OK", jsonschema.validate.__name__)'
python3 -u "$ROOT/command-center/p2-wave/seed-stage/_diag_g1_samples.py"
