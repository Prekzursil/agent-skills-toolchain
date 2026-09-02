#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1"
OUT="$HOME/p2-g1-shard00-measure.jsonl"
IDS=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-00.txt
ok=0
fail=0
n=0
: > "$OUT"
while IFS= read -r uid || [ -n "$uid" ]; do
  uid=$(printf '%s' "$uid" | tr -d '\r')
  [ -z "$uid" ] && continue
  n=$((n+1))
  echo "===== MEASURE $uid ($n) ====="
  log=/tmp/g1-"$uid".out
  python3 -B command-center/p2-wave/_measure_one_delivered.py "$uid" >"$log" 2>&1 < /dev/null
  rc=$?
  line=$(tail -n 1 "$log")
  echo "$line"
  if grep -q 'SUCCESS:delivered' "$log"; then
    ok=$((ok+1))
    printf '{"id":"%s","ok":true,"rc":%s}\n' "$uid" "$rc" >> "$OUT"
  else
    fail=$((fail+1))
    printf '{"id":"%s","ok":false,"rc":%s}\n' "$uid" "$rc" >> "$OUT"
    echo "TAIL $uid:"
    tail -n 12 "$log"
  fi
done < "$IDS"
echo "BATCH ok=$ok fail=$fail n=$n"
echo "SUCCESS:shard00-measure ok=$ok fail=$fail n=$n"
