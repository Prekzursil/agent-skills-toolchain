#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1"
OUT=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard20_near.jsonl
: > "$OUT"
ok=0
fail=0
while IFS= read -r id; do
  id=${id%$'\r'}
  [ -z "$id" ] && continue
  echo "=== NEAR $id ==="
  log=$(mktemp)
  timeout 180 python3 command-center/p2-wave/_measure_one_delivered.py "$id" >"$log" 2>&1
  rc=$?
  tail -n 10 "$log"
  last=$(tail -n 1 "$log")
  if echo "$last" | grep -q "^SUCCESS:delivered $id$"; then
    ok=$((ok+1))
    printf '{"id":"%s","ok":true}\n' "$id" >> "$OUT"
  else
    fail=$((fail+1))
    reason=$(grep -E '^FAILED:delivered' "$log" | tail -n 1 | tr '"' "'")
    printf '{"id":"%s","ok":false,"reason":"%s"}\n' "$id" "$reason" >> "$OUT"
  fi
  rm -f "$log"
done < /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_s20_near.txt
echo "NEAR attempted=6 ok=$ok fail=$fail"
