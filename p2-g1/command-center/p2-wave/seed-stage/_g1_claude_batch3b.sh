#!/usr/bin/env bash
# Batch 3b: push changed files to mirror, run TST-0007 + IMP-0417 chains.
set -u
WIN=/mnt/c/Users/Prekzursil/source/ast-integrate
M="$HOME/p2-g1"
export AST_INTEGRATE_ROOT="$M"
cp "$WIN/lib/completion_reducer.py" "$M/lib/completion_reducer.py"
mkdir -p "$M/tools/completion/tests"
cp "$WIN/tools/completion/census.py" "$M/tools/completion/census.py"
cp "$WIN/tools/completion/tests/test_import_graph.py" "$M/tools/completion/tests/test_import_graph.py"
cd "$M"

echo "=== TST-0007 suite"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0007/suite.py 2>&1 | tail -3
echo "=== TST-0007 emit"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0007/emit_receipt.py 2>&1 | tail -3
echo "=== TST-0007 probes"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0007/probe1_histogram.py 2>&1 | tail -2
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0007/probe2_default_exercised.py 2>&1 | tail -2

echo "=== IMP-0417 tests standalone"
PYTHONDONTWRITEBYTECODE=1 python3 -B tools/completion/tests/test_import_graph.py 2>&1 | tail -3
echo "=== IMP-0417 probes"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0417/probe1_import_graph.py 2>&1 | tail -2
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0417/probe2_planted_predicate.py 2>&1 | tail -2
