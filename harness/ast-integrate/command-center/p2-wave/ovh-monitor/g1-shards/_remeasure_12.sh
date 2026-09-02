#!/usr/bin/env bash
set -u
bash /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/seed-stage/_g1_rsync.sh
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1" || exit 2
ids='ARC-0082 AUD-0024 CC-0006 CNF-0183 IMP-0019 IMP-0034 IMP-0037 IMP-0045 IMP-0050 IMP-0046 IMP-0055 IMP-0069'
ok=0
fail=0
out=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_remeasure_12.log
: > "$out"
for id in $ids; do
  echo "==== ${id}" | tee -a "$out"
  if python3 command-center/p2-wave/_measure_one_delivered.py "${id}" 2>&1 | tee -a "$out" | tail -n 1 | grep -q '^SUCCESS:delivered '; then
    ok=$((ok + 1))
  else
    fail=$((fail + 1))
  fi
done
echo "SUMMARY ok=${ok} fail=${fail}" | tee -a "$out"
