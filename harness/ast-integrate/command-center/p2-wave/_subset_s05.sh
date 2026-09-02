#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="${AST_INTEGRATE_ROOT:-$HOME/p2-g1}"
cd "$AST_INTEGRATE_ROOT"
ok=0
fail=0
ids='ADV-0091 ADV-0016 ADV-0111 ARC-0050 CC-0001 CNF-0104 CNL-0063 CNL-0113 IMP-0018 IMP-0412 IMP-0480 RES-0102 ADV-0033 ADV-0066 AUD-0018 IMP-0040 IMP-0064 IMP-0161 IMP-0230 IMP-0357 IMP-0396 IMP-0423 TST-0162'
for id in $ids; do
  echo "==== $id"
  if python3 command-center/p2-wave/_measure_one_delivered.py "$id"; then
    ok=$((ok+1))
  else
    fail=$((fail+1))
  fi
done
echo SUBSET-SUMMARY ok=$ok fail=$fail
