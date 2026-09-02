#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT=$HOME/p2-g1
cd "$AST_INTEGRATE_ROOT" || exit 2
export PYTHONDONTWRITEBYTECODE=1
LOG=$HOME/p2-g1-shard03-measure.log
JSONL=$HOME/p2-g1-shard03-measure.jsonl
: > "$LOG"
: > "$JSONL"
IDS_FILE=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-03.txt
ok=0
fail=0
n=0
while IFS= read -r id; do
  [ -z "$id" ] && continue
  n=$((n+1))
  echo "===== $id ($n) =====" | tee -a "$LOG"
  out=$(python3 command-center/p2-wave/_measure_one_delivered.py "$id" 2>&1)
  rc=$?
  echo "$out" | tee -a "$LOG"
  last=$(echo "$out" | tail -n 1)
  if echo "$last" | grep -q "^SUCCESS:delivered $id$"; then
    ok=$((ok+1))
    status=ok
  else
    fail=$((fail+1))
    status=fail
  fi
  python3 - <<PY
import json
rec = {
  "id": "$id",
  "rc": $rc,
  "status": "$status",
  "line": """$last""".strip(),
}
print(json.dumps(rec))
PY
  echo "$out" | tail -n 12 >> "$JSONL"
  echo "----- $status $id rc=$rc -----" >> "$JSONL"
done < "$IDS_FILE"
echo "SUMMARY attempted=$n ok=$ok fail=$fail" | tee -a "$LOG"
echo MEASURE-DONE | tee -a "$LOG"
