#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1"
OUT="/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard16_g1.jsonl"
: > "$OUT"
IDS=$(tr -d '\r' < /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-16.txt)
ok=0
fail=0
for id in $IDS; do
  [ -z "$id" ] && continue
  echo "=== $id ==="
  if python3 command-center/p2-wave/_measure_one_delivered.py "$id" > "/tmp/g1-$id.log" 2>&1; then
    echo "SUCCESS:delivered $id"
    echo "{\"id\":\"$id\",\"ok\":true}" >> "$OUT"
    ok=$((ok+1))
  else
    echo "FAILED:delivered $id"
    tail -n 12 "/tmp/g1-$id.log"
    reason=$(grep -E '^FAILED:delivered' "/tmp/g1-$id.log" | tail -n 1 | tr '"' "'")
    echo "{\"id\":\"$id\",\"ok\":false,\"reason\":\"$reason\"}" >> "$OUT"
    fail=$((fail+1))
  fi
done
echo "DONE ok=$ok fail=$fail"
