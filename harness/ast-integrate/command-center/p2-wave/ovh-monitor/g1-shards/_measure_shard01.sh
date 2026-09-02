#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT=$HOME/p2-g1
cd "$AST_INTEGRATE_ROOT" || exit 2
LOG=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard01_measure.log
: > "$LOG"
ok=0
fail=0
attempted=0
while IFS= read -r id || [ -n "$id" ]; do
  id="${id%$'\r'}"
  [ -z "$id" ] && continue
  attempted=$((attempted+1))
  echo "===== $id =====" | tee -a "$LOG"
  if python3 command-center/p2-wave/_measure_one_delivered.py "$id" >>"$LOG" 2>&1 </dev/null; then
    echo "OK $id" | tee -a "$LOG"
    ok=$((ok+1))
  else
    echo "FAIL $id" | tee -a "$LOG"
    fail=$((fail+1))
  fi
done < /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-01.txt
echo "MEASURE-SUMMARY attempted=$attempted ok=$ok fail=$fail" | tee -a "$LOG"
echo MEASURE-DONE | tee -a "$LOG"
