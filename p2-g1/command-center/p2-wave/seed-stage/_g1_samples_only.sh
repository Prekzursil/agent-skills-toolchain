#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
export AST_INTEGRATE_ROOT="$SRC"
cd "$SRC"
SITE=$(python3 -c 'import site; print(site.getusersitepackages())')
mkdir -p "$SITE"
cp command-center/p2-wave/seed-stage/p2_jsonschema_hook.py "$SITE/p2_jsonschema_hook.py"
cp command-center/p2-wave/seed-stage/sitecustomize_jsonschema.py "$SITE/sitecustomize.py"
printf 'import p2_jsonschema_hook\n' > "$SITE/p2g1.pth"
python3 -c 'import p2_jsonschema_hook; print("HOOK-OK")'
python3 -u command-center/p2-wave/seed-stage/_diag_g1_samples.py
