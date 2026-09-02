#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT=$HOME/p2-g1
cd "$AST_INTEGRATE_ROOT" || exit 2
export PYTHONDONTWRITEBYTECODE=1
LOG=$HOME/p2-g1-s03-measure.log
JSONL=$HOME/p2-g1-s03-measure.jsonl
TMP=$HOME/p2-g1-s03-one.out
IDS_FILE=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-03.txt
: > "$LOG"
: > "$JSONL"
ok=0
fail=0
n=0
while IFS= read -r id || [ -n "$id" ]; do
  id=${id%$'\r'}
  id=${id//$'\r'/}
  [ -z "$id" ] && continue
  n=$((n+1))
  echo "===== $id ($n) =====" | tee -a "$LOG"
  python3 command-center/p2-wave/_measure_one_delivered.py "$id" > "$TMP" 2>&1
  rc=$?
  cat "$TMP" | tee -a "$LOG"
  last=$(tail -n 1 "$TMP")
  if [ "$last" = "SUCCESS:delivered $id" ]; then
    ok=$((ok+1))
    status=ok
  else
    fail=$((fail+1))
    status=fail
  fi
  python3 - "$id" "$rc" "$status" "$last" "$TMP" "$JSONL" <<'PY'
import json, sys
uid, rc, status, last, tmp, jsonl = sys.argv[1:7]
text = open(tmp, encoding="utf-8", errors="replace").read()
rec = {"id": uid, "rc": int(rc), "status": status, "line": last, "tail": text[-3500:]}
with open(jsonl, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
PY
  echo "----- $status $id rc=$rc n=$n ok=$ok fail=$fail -----" | tee -a "$LOG"
done < "$IDS_FILE"
echo "SUMMARY attempted=$n ok=$ok fail=$fail" | tee -a "$LOG"
echo MEASURE-DONE | tee -a "$LOG"
