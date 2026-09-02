#!/usr/bin/env bash
# Batch 5b: TST-0126 noop census — push files, run probes, receipts, measure.
set -u
WIN=/mnt/c/Users/Prekzursil/source/ast-integrate
M="$HOME/p2-g1"
export AST_INTEGRATE_ROOT="$M"

cp "$WIN/tools/testinfra/noop_census.py" "$M/tools/testinfra/noop_census.py"
cp "$WIN/tools/testinfra/test_noop_census.py" "$M/tools/testinfra/test_noop_census.py"

cd "$M"
echo "=== probe1"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0126/probe1_planted_shapes.py 2>&1 | tail -3
echo "=== probe2"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0126/probe2_negatives.py 2>&1 | tail -3
echo "=== write_receipts"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0126/write_receipts.py 2>&1 | tail -3

cp "$M/command-center/receipts/TST-0126.json" "$WIN/command-center/receipts/TST-0126.json"
cp "$M/command-center/p2-wave/probes/TST-0126/SUBAGENT-RETURN.json" "$WIN/command-center/p2-wave/probes/TST-0126/SUBAGENT-RETURN.json"
cp "$M/command-center/p2-wave/probes/TST-0126/UNIT-ARTIFACT-MANIFEST.json" "$WIN/command-center/p2-wave/probes/TST-0126/UNIT-ARTIFACT-MANIFEST.json"

echo "=== measure TST-0126"
python3 command-center/p2-wave/_measure_one_delivered.py TST-0126 2>&1 | tail -1
