#!/usr/bin/env bash
# Batch 4b: TST-0150 receipts + canonical mirror measure.
set -u
WIN=/mnt/c/Users/Prekzursil/source/ast-integrate
M="$HOME/p2-g1"
export AST_INTEGRATE_ROOT="$M"
P=command-center/p2-wave/probes/TST-0150
cd "$M"
PYTHONDONTWRITEBYTECODE=1 python3 -B "$P/write_receipts.py" 2>&1 | tail -2
cp "$M/command-center/receipts/TST-0150.json" "$WIN/command-center/receipts/TST-0150.json"
cp "$M/$P/SUBAGENT-RETURN.json" "$M/$P/UNIT-ARTIFACT-MANIFEST.json" "$WIN/$P/"
cp "$M/$P/probe1-both-states.raw.json" "$M/$P/probe2-memory-only.raw.json" "$WIN/$P/" 2>/dev/null || true
python3 command-center/p2-wave/_measure_one_delivered.py TST-0150 2>&1 | tail -1
