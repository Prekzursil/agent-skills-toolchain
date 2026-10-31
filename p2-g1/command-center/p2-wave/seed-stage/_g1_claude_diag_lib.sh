#!/usr/bin/env bash
set -uo pipefail
DST="$HOME/p2-g1"
export AST_INTEGRATE_ROOT="$DST"
cd "$DST"
export PYTHONPATH="$DST/command-center/p2-wave/seed-stage:$DST:$DST/tools:$DST/tools/measure-guard:$DST/platform/lib:$DST/tools/agentspec"
python3 - <<'EOF'
import sys
try:
    import lib
    print("lib ->", getattr(lib, "__file__", None), getattr(lib, "__path__", None))
except Exception as e:
    print("import lib failed:", e)
try:
    import lib.completion_reducer as cr
    print("completion_reducer ->", cr.__file__)
except Exception as e:
    print("import lib.completion_reducer failed:", type(e).__name__, e)
import os
print("tools/lib __init__?", os.path.exists("tools/lib/__init__.py"))
print("platform/lib exists?", os.path.exists("platform/lib"))
EOF
