#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT=/home/prekzursil/p2-g1
export PYTHONDONTWRITEBYTECODE=1
cd /home/prekzursil/p2-g1 || exit 2
ids="ARC-0035 BLD-0024 BLD-0058 CNF-0140 IMP-0106 IMP-0354 RES-0026 RES-0145 IMP-0226 IMP-0249 IMP-0280 IMP-0385 TST-0190 IMP-0085 IMP-0015"
out=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard02_close.jsonl
: > "$out"
ok=0
fail=0
for id in $ids; do
  tmp=$(mktemp)
  python3 command-center/p2-wave/_measure_one_delivered.py "$id" >"$tmp" 2>&1
  last=$(tail -n 1 "$tmp")
  echo "$last"
  if printf '%s\n' "$last" | grep -q '^SUCCESS:delivered '; then
    ok=$((ok + 1))
    status=ok
  else
    fail=$((fail + 1))
    status=fail
  fi
  python3 -c 'import json,sys; print(json.dumps({"id":sys.argv[1],"status":sys.argv[2],"last":sys.argv[3]}))' \
    "$id" "$status" "$last" >> "$out"
  rm -f "$tmp"
done
echo "SUMMARY ok=${ok} fail=${fail}"
