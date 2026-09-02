#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1" || exit 2
export PYTHONDONTWRITEBYTECODE=1
OUT=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard21_g1_retry.jsonl
: > "$OUT"
ids='IMP-0056 IMP-0403 TST-0216 TST-0119 TST-0341 WFA-0101'
n=0
ok=0
fail=0
for id in $ids; do
  n=$((n+1))
  echo "===== $id ====="
  text=$(python3 command-center/p2-wave/_measure_one_delivered.py "$id" 2>&1)
  last=$(printf '%s\n' "$text" | tail -n 1)
  printf '%s\n' "$text" | tail -n 14
  case "$last" in
    SUCCESS:delivered*) ok=$((ok+1)); mark=1 ;;
    *) fail=$((fail+1)); mark=0 ;;
  esac
  python3 -c 'import json,sys; print(json.dumps({"id":sys.argv[1],"ok":sys.argv[2]=="1","last":sys.argv[3]}))' "$id" "$mark" "$last" >> "$OUT"
done
echo SUMMARY attempted=$n ok=$ok fail=$fail
