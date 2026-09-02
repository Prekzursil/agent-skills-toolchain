#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1" || exit 2
export PYTHONDONTWRITEBYTECODE=1
OUT=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard21_g1_rest.jsonl
: > "$OUT"
ids='IMP-0009 IMP-0032 IMP-0056 IMP-0323 IMP-0346 IMP-0403 IMP-0440 CNF-0034 CNF-0091 CNF-0177 CNL-0097 BLD-0015 BLD-0011 ADV-0135 ARC-0022 ARC-0066 AUD-0009 CC-0019 IMP-0081 IMP-0102 IMP-0127 IMP-0157 IMP-0193 IMP-0222 IMP-0255 IMP-0273 IMP-0299 IMP-0370 IMP-0471 RES-0135 RES-0167 SYN-0001 SYN-0044 TST-0019 TST-0077 TST-0119 TST-0150 TST-0182 TST-0216 TST-0251 TST-0272 TST-0304 TST-0341 WFA-0061 WFA-0101 WFA-0146 ADV-0023'
n=0
ok=0
fail=0
for id in $ids; do
  n=$((n+1))
  echo "===== $id ====="
  text=$(python3 command-center/p2-wave/_measure_one_delivered.py "$id" 2>&1)
  last=$(printf '%s\n' "$text" | tail -n 1)
  printf '%s\n' "$text" | tail -n 12
  case "$last" in
    SUCCESS:delivered*) ok=$((ok+1)); mark=1 ;;
    *) fail=$((fail+1)); mark=0 ;;
  esac
  python3 -c 'import json,sys; print(json.dumps({"id":sys.argv[1],"ok":sys.argv[2]=="1","last":sys.argv[3]}))' "$id" "$mark" "$last" >> "$OUT"
done
echo SUMMARY attempted=$n ok=$ok fail=$fail
