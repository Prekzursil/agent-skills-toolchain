#!/usr/bin/env bash
# Batch 3c: regenerate receipts, copy back to Windows, measure 4 units.
set -u
WIN=/mnt/c/Users/Prekzursil/source/ast-integrate
M="$HOME/p2-g1"
export AST_INTEGRATE_ROOT="$M"
cd "$M"

for id in TST-0007 IMP-0417 TST-0316; do
  echo "=== $id write_receipts"
  PYTHONDONTWRITEBYTECODE=1 python3 -B "command-center/p2-wave/probes/$id/write_receipts.py" 2>&1 | tail -2
  cp "$M/command-center/receipts/$id.json" "$WIN/command-center/receipts/$id.json"
  cp "$M/command-center/p2-wave/probes/$id/SUBAGENT-RETURN.json" "$WIN/command-center/p2-wave/probes/$id/SUBAGENT-RETURN.json"
  cp "$M/command-center/p2-wave/probes/$id/UNIT-ARTIFACT-MANIFEST.json" "$WIN/command-center/p2-wave/probes/$id/UNIT-ARTIFACT-MANIFEST.json"
done

for id in TST-0007 IMP-0417 TST-0316 IMP-0415; do
  echo "=== measure $id"
  python3 command-center/p2-wave/_measure_one_delivered.py "$id" 2>&1 | tail -1
done
