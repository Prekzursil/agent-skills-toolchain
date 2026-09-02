#!/usr/bin/env bash
# Batch 5: IMP-0471 detectors package — push files, run chain, emit, measure.
set -u
WIN=/mnt/c/Users/Prekzursil/source/ast-integrate
M="$HOME/p2-g1"
export AST_INTEGRATE_ROOT="$M"

mkdir -p "$M/tools/detectors/tests"
for f in two_state.py adapters.py census.py campaign.py; do
  cp "$WIN/tools/detectors/$f" "$M/tools/detectors/$f"
done
cp "$WIN/tools/detectors/tests/test_two_state_harness.py" "$M/tools/detectors/tests/test_two_state_harness.py"

cd "$M"
echo "=== harness tests"
PYTHONDONTWRITEBYTECODE=1 python3 -B tools/detectors/tests/test_two_state_harness.py 2>&1 | tail -3
echo "=== emit_receipt"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0471/emit_receipt.py 2>&1 | tail -3
echo "=== probe1"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0471/probe1_two_state_table.py 2>&1 | tail -4
echo "=== probe2"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0471/probe2_reviewer_independent_broken.py 2>&1 | tail -4

cp "$M/command-center/receipts/IMP-0471.json" "$WIN/command-center/receipts/IMP-0471.json"
cp "$M/command-center/p2-wave/probes/IMP-0471/SUBAGENT-RETURN.json" "$WIN/command-center/p2-wave/probes/IMP-0471/SUBAGENT-RETURN.json"
cp "$M/command-center/p2-wave/probes/IMP-0471/UNIT-ARTIFACT-MANIFEST.json" "$WIN/command-center/p2-wave/probes/IMP-0471/UNIT-ARTIFACT-MANIFEST.json"

for id in IMP-0471 TST-0126; do
  echo "=== measure $id"
  python3 command-center/p2-wave/_measure_one_delivered.py "$id" 2>&1 | tail -1
done
