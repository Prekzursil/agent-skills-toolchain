#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1" || exit 2
ok=0
fail=0
attempted=0
outdir="$HOME/p2-g1-measure-envelope-rest"
mkdir -p "$outdir"
ids="ARC-0024 CNF-0001 CNF-0063 ARC-0058"
for id in $ids; do
  attempted=$((attempted + 1))
  echo "======== MEASURE $id ========"
  logfile="$outdir/${id}.log"
  python3 command-center/p2-wave/_measure_one_delivered.py "$id" >"$logfile" 2>&1
  rc=$?
  tail -n 30 "$logfile"
  echo "exit=$rc"
  if grep -q "^SUCCESS:delivered $id" "$logfile"; then
    echo "RESULT $id SUCCESS"
    ok=$((ok + 1))
  else
    echo "RESULT $id FAIL"
    fail=$((fail + 1))
  fi
done
echo "ATTEMPTED=$attempted OK=$ok FAIL=$fail"
