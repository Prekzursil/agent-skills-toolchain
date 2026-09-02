#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1"
export PYTHONDONTWRITEBYTECODE=1
IDS="${1:-command-center/p2-wave/seed-stage/_class_mod_ids.txt}"
OUT="${2:-/tmp/g1-class-mod.measure.jsonl}"
: > "$OUT"
ok=0
fail=0
n=0
while IFS= read -r uid; do
  [ -z "$uid" ] && continue
  n=$((n+1))
  echo "===== MEASURE $uid ($n) ====="
  line=$(python3 -B command-center/p2-wave/_measure_one_delivered.py "$uid" | tee /tmp/g1-one.out | tail -n 1)
  echo "$line"
  if echo "$line" | grep -q '^SUCCESS:delivered '; then
    ok=$((ok+1))
    printf '{"id":"%s","ok":true,"line":"%s"}\n' "$uid" "$line" >> "$OUT"
  else
    fail=$((fail+1))
    tail=$(tail -n 20 /tmp/g1-one.out | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])')
    printf '{"id":"%s","ok":false,"line":"%s"}\n' "$uid" "$line" >> "$OUT"
    echo "FAIL-TAIL $uid"
    tail -n 12 /tmp/g1-one.out
  fi
done < "$IDS"
echo "===== SUMMARY n=$n ok=$ok fail=$fail ====="
echo "FAILED:g1-class-mod ok=$ok fail=$fail n=$n"
exit 0
