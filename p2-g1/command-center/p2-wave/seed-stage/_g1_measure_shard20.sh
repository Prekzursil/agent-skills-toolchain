#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1"
IDS_FILE=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-20.txt
OUT=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard20_g1.jsonl
: > "$OUT"
ok=0
fail=0
n=0
while IFS= read -r id; do
  id=${id%$'\r'}
  [ -z "$id" ] && continue
  n=$((n+1))
  echo "=== MEASURE $id ==="
  log=$(mktemp)
  timeout 180 python3 command-center/p2-wave/_measure_one_delivered.py "$id" >"$log" 2>&1
  rc=$?
  tail -n 16 "$log"
  last=$(tail -n 1 "$log")
  if echo "$last" | grep -q "^SUCCESS:delivered $id$"; then
    ok=$((ok+1))
    printf '{"id":"%s","ok":true,"rc":%s}\n' "$id" "$rc" >> "$OUT"
  else
    fail=$((fail+1))
    reason=$(grep -E '^FAILED:delivered' "$log" | tail -n 1 | tr '"' "'")
    printf '{"id":"%s","ok":false,"rc":%s,"reason":"%s"}\n' "$id" "$rc" "$reason" >> "$OUT"
  fi
  rm -f "$log"
done < "$IDS_FILE"
echo "G1-SHARD20 attempted=$n ok=$ok fail=$fail"
