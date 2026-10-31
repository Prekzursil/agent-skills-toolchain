#!/usr/bin/env bash
# Batch 3: TST-0007 (stale lib), IMP-0417 (tests file), TST-0316 (cross_vendor pkg).
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
WIN=/mnt/c/Users/Prekzursil/source/ast-integrate
bash "$WIN/command-center/p2-wave/seed-stage/_g1_rsync.sh" >/dev/null 2>&1
cd "$HOME/p2-g1"
# stale artifacts the rsync (no --delete) leaves behind
rm -rf command-center/p2-wave/probes/TST-0007/lib command-center/p2-wave/probes/TST-0007/__pycache__
rm -f tools/cross_vendor.py

for id in TST-0007 IMP-0417 TST-0316; do
  echo "=== $id probes"
  for p in command-center/p2-wave/probes/$id/probe*.py; do
    PYTHONDONTWRITEBYTECODE=1 python3 -B "$p" >/tmp/g1b3.out 2>&1
    rc=$?
    echo "-- $p rc=$rc"
    tail -3 /tmp/g1b3.out
  done
done
