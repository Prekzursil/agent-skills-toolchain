#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT=/home/prekzursil/p2-g1
export PYTHONDONTWRITEBYTECODE=1
cd /home/prekzursil/p2-g1 || exit 2
ids="ADV-0007 ADV-0030 ADV-0064 ADV-0086 AUD-0015 CNF-0001 CNL-0109 IMP-0039 IMP-0135 IMP-0414 IMP-0474 TST-0001 TST-0218 WFA-0111 ADV-0055 IMP-0062 IMP-0158 IMP-0327 WFA-0070 IMP-0106 IMP-0354 IMP-0226 IMP-0385"
out=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard02_ok_verify.jsonl
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
