#!/usr/bin/env bash
# Batch 6b: WFA-0134 retry after path-stable reason fix.
set -u
WIN=/mnt/c/Users/Prekzursil/source/ast-integrate
M="$HOME/p2-g1"
export AST_INTEGRATE_ROOT="$M"

cp "$WIN/tools/foundry/completion_predicate.py" "$M/tools/foundry/completion_predicate.py"
cd "$M"

echo "=== WFA-0134 write_receipts"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/WFA-0134/write_receipts.py 2>&1 | tail -4

echo "=== copy back"
cp "$M/tools/foundry/completion_predicate.py" "$WIN/tools/foundry/completion_predicate.py" 2>/dev/null || true
ART=$(ls "$M"/command-center/foundry/WFA-0134-*.json 2>/dev/null | head -1)
if [ -n "${ART:-}" ]; then
  mkdir -p "$WIN/command-center/foundry"
  cp "$ART" "$WIN/command-center/foundry/$(basename "$ART")"
fi
cp "$M/command-center/p2-wave/probes/WFA-0134/SUBAGENT-RETURN.json" "$WIN/command-center/p2-wave/probes/WFA-0134/SUBAGENT-RETURN.json" 2>/dev/null || echo "no return"
cp "$M/command-center/p2-wave/probes/WFA-0134/UNIT-ARTIFACT-MANIFEST.json" "$WIN/command-center/p2-wave/probes/WFA-0134/UNIT-ARTIFACT-MANIFEST.json" 2>/dev/null || echo "no manifest"

echo "=== measure"
python3 command-center/p2-wave/_measure_one_delivered.py WFA-0134 2>&1 | tail -1
