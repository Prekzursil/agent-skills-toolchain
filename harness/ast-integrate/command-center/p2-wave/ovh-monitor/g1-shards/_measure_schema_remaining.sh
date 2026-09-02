#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1"
LOG=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/class-schema.remeasure.log
: > "$LOG"
for id in AUD-0059 CC-0019 CNF-0072 WFA-0148; do
  echo "==== MEASURE $id ====" | tee -a "$LOG"
  python3 command-center/p2-wave/_measure_one_delivered.py "$id" >> "$LOG" 2>&1
  rc=$?
  echo "==== END $id rc=$rc ====" | tee -a "$LOG"
done
echo ALL-DONE | tee -a "$LOG"
