#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT=/home/prekzursil/p2-g1
cd /home/prekzursil/p2-g1
ids='ADV-0015 IMP-0092 TST-0166 TST-0137 IMP-0208 TST-0203 TST-0022 TST-0055 IMP-0263 IMP-0311 TST-0227 IMP-0336 REL-0010 IMP-0118 TST-0317'
ok=0
fail=0
for id in $ids; do
  echo "===== $id"
  last=$(python3 -B command-center/p2-wave/_measure_one_delivered.py "$id" | tee /tmp/m-$id.out | tail -n 1)
  echo "$last"
  if printf '%s\n' "$last" | grep -q '^SUCCESS:delivered '; then
    ok=$((ok+1))
  else
    fail=$((fail+1))
    tail -n 8 /tmp/m-$id.out
  fi
done
echo "SUMMARY ok=$ok fail=$fail"
