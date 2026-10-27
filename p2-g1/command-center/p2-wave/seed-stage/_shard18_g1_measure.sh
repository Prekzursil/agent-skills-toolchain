#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="${AST_INTEGRATE_ROOT:-$HOME/p2-g1}"
cd "$AST_INTEGRATE_ROOT"
OUT="/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard18_g1.jsonl"
IDS="$AST_INTEGRATE_ROOT/command-center/p2-wave/seed-stage/_shard18_ids.txt"
: > "$OUT"
ok=0
fail=0
n=0
while IFS= read -r id; do
  [ -z "$id" ] && continue
  n=$((n+1))
  echo "MEASURE $id" >&2
  log=$(mktemp)
  python3 command-center/p2-wave/_measure_one_delivered.py "$id" >"$log" 2>&1
  rc=$?
  last=$(tail -n 1 "$log" | tr -d '\r')
  if echo "$last" | grep -q "SUCCESS:delivered"; then
    ok=$((ok+1))
    echo "{\"id\":\"$id\",\"ok\":true,\"rc\":$rc,\"last\":$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$last")}" >> "$OUT"
    echo "OK $id" >&2
  else
    fail=$((fail+1))
    tail8=$(tail -n 8 "$log" | tr '\n' '|' | tr -d '\r')
    echo "{\"id\":\"$id\",\"ok\":false,\"rc\":$rc,\"last\":$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$last"),\"tail\":$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1][:1500]))' "$tail8")}" >> "$OUT"
    echo "FAIL $id $last" >&2
  fi
  rm -f "$log"
done < "$IDS"
echo "DONE attempted=$n ok=$ok fail=$fail" >&2
echo "DONE attempted=$n ok=$ok fail=$fail"
