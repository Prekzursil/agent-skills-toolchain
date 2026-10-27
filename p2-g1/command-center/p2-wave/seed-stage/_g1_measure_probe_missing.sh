#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="${AST_INTEGRATE_ROOT:-$HOME/p2-g1}"
cd "$AST_INTEGRATE_ROOT" || exit 2
fail=0
for id in ADV-0041 IMP-0015 IMP-0420 TST-0115; do
  echo "==== MEASURE $id ===="
  python3 command-center/p2-wave/_measure_one_delivered.py "$id"
  rc=$?
  echo "MEASURE_RC $id $rc"
  if [ "$rc" -ne 0 ]; then
    fail=1
  fi
done
exit "$fail"
