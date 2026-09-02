#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="${AST_INTEGRATE_ROOT:-$HOME/p2-g1}"
cd "$AST_INTEGRATE_ROOT"
OUT=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard18_g1.jsonl
IDS=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/seed-stage/_shard18_ids_rest.txt
ok=0
fail=0
n=0
while IFS= read -r id || [ -n "$id" ]; do
  id="${id%$'\r'}"
  [ -z "$id" ] && continue
  n=$((n + 1))
  echo "MEASURE $id"
  log=$(mktemp)
  python3 command-center/p2-wave/_measure_one_delivered.py "$id" >"$log" 2>&1
  rc=$?
  last=$(tail -n 1 "$log" | tr -d '\r')
  if echo "$last" | grep -q "SUCCESS:delivered"; then
    ok=$((ok + 1))
    echo "OK $id"
    python3 -c 'import json,sys; open(sys.argv[1],"a",encoding="utf-8").write(json.dumps({"id":sys.argv[2],"ok":True,"rc":int(sys.argv[3]),"last":sys.argv[4]})+"\n")' "$OUT" "$id" "$rc" "$last"
  else
    fail=$((fail + 1))
    echo "FAIL $id $last"
    tail6=$(tail -n 6 "$log" | tr '\n' '|')
    python3 -c 'import json,sys; open(sys.argv[1],"a",encoding="utf-8").write(json.dumps({"id":sys.argv[2],"ok":False,"rc":int(sys.argv[3]),"last":sys.argv[4],"tail":sys.argv[5][:1500]})+"\n")' "$OUT" "$id" "$rc" "$last" "$tail6"
  fi
  rm -f "$log"
done < "$IDS"
echo "DONE attempted=$n ok=$ok fail=$fail"
