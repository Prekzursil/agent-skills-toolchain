#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1" || exit 2
ids='ARC-0082 AUD-0024 CC-0006 CNF-0183 IMP-0019 IMP-0034 IMP-0037 IMP-0045 IMP-0050 IMP-0046 IMP-0055 IMP-0069'
ok=0
fail=0
for id in $ids; do
  echo "==== ${id}"
  if python3 command-center/p2-wave/_measure_one_delivered.py "${id}"; then
    ok=$((ok + 1))
  else
    fail=$((fail + 1))
  fi
done
echo "SUMMARY ok=${ok} fail=${fail}"
