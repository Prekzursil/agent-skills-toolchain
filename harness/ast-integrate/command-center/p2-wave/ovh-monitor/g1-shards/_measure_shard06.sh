#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="${AST_INTEGRATE_ROOT:-$HOME/p2-g1}"
cd "$AST_INTEGRATE_ROOT"
LOG="/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard06_measure.log"
JSONL="/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard06_measure.jsonl"
IDS="/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-06.txt"
: > "$LOG"
: > "$JSONL"
ok=0
fail=0
n=0
while IFS= read -r uid; do
  uid="${uid%%$'\r'}"
  [ -z "$uid" ] && continue
  n=$((n+1))
  echo "===== $uid =====" | tee -a "$LOG"
  out=$(python3 -B command-center/p2-wave/_measure_one_delivered.py "$uid" 2>&1) || true
  echo "$out" | tee -a "$LOG"
  last=$(echo "$out" | awk 'NF{line=$0} END{print line}')
  if [ "$last" = "SUCCESS:delivered $uid" ]; then
    ok=$((ok+1))
    status=ok
  else
    fail=$((fail+1))
    status=fail
  fi
  python3 - <<PY
import json
rec={"id":"$uid","status":"$status","last":"""$last"""}
open(r"$JSONL","a",encoding="utf-8").write(json.dumps(rec)+"\n")
PY
  echo "PROGRESS n=$n ok=$ok fail=$fail last=$last" | tee -a "$LOG"
done < "$IDS"
echo "SUMMARY attempted=$n ok=$ok fail=$fail" | tee -a "$LOG"
