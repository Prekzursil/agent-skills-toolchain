#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1" || exit 2
export PYTHONDONTWRITEBYTECODE=1
OUT=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard21_g1_pass.jsonl
: > "$OUT"
ids='ADV-0056 ADV-0084 ADV-0107 AUD-0039 AUD-0074 BLD-0015 CNF-0136 CNL-0045 RES-0014 RES-0079'
for id in $ids; do
  echo "===== $id ====="
  text=$(python3 command-center/p2-wave/_measure_one_delivered.py "$id" 2>&1)
  last=$(printf '%s\n' "$text" | tail -n 1)
  printf '%s\n' "$text" | tail -n 16
  python3 -c 'import json,sys; print(json.dumps({"id":sys.argv[1],"last":sys.argv[2],"ok":sys.argv[2].startswith("SUCCESS:delivered")}))' "$id" "$last" >> "$OUT"
done
echo DONE-PASS
