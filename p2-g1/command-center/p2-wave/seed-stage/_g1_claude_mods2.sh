#!/usr/bin/env bash
# Measure the remaining ModuleNotFoundError units and show tails.
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1"
for id in IMP-0417 IMP-0471 TST-0114 TST-0150 TST-0316 TST-0007; do
  echo "== $id"
  python3 command-center/p2-wave/_measure_one_delivered.py "$id" 2>&1 | tail -2
done
