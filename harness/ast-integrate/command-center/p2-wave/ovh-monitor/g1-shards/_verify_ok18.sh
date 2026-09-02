#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT=/home/prekzursil/p2-g1
cd /home/prekzursil/p2-g1 || exit 2
ids='ADV-0037 ADV-0092 ARC-0005 ARC-0049 AUD-0021 BLD-0034 CC-0005 CNL-0016 CNL-0119 IMP-0019 IMP-0045 IMP-0070 IMP-0092 IMP-0336 IMP-0424 RES-0040 TST-0166 WFA-0018'
out=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard09_verify_ok18.jsonl
: > "$out"
ok=0
fail=0
for id in $ids; do
  echo "===== $id"
  tmp=$(mktemp)
  python3 -B command-center/p2-wave/_measure_one_delivered.py "$id" >"$tmp" 2>&1
  last=$(tail -n 1 "$tmp")
  echo "$last"
  if printf '%s\n' "$last" | grep -q "^SUCCESS:delivered $id"; then
    ok=$((ok+1))
    status=ok
  else
    fail=$((fail+1))
    status=fail
    tail -n 6 "$tmp"
  fi
  python3 -c 'import json,sys; print(json.dumps({"id":sys.argv[1],"ok":sys.argv[2]=="ok","last":sys.argv[3]}))' "$id" "$status" "$last" >> "$out"
  rm -f "$tmp"
done
echo "VERIFY-OK18 attempted=18 ok=$ok fail=$fail"
