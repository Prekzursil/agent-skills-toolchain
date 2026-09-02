#!/usr/bin/env bash
set -u
if [ "${SKIP_RSYNC:-0}" != "1" ]; then
  bash /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/seed-stage/_g1_rsync.sh
fi
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1" || exit 2
ids_file=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard02_fail_ids.txt
out=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard02_fail_remeasure.log
jsonl=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard02_fail_remeasure.jsonl
: > "$out"
: > "$jsonl"
ok=0
fail=0
attempted=0
while IFS= read -r id || [ -n "$id" ]; do
  id="${id%$'\r'}"
  [ -z "$id" ] && continue
  attempted=$((attempted + 1))
  echo "==== ${id}" | tee -a "$out"
  tmp=$(mktemp)
  python3 command-center/p2-wave/_measure_one_delivered.py "${id}" >"$tmp" 2>&1
  rc=$?
  cat "$tmp" | tee -a "$out"
  last=$(tail -n 1 "$tmp")
  if printf '%s\n' "$last" | grep -q '^SUCCESS:delivered '; then
    ok=$((ok + 1))
    status=ok
  else
    fail=$((fail + 1))
    status=fail
  fi
  python3 -c 'import json,sys; print(json.dumps({"id":sys.argv[1],"rc":int(sys.argv[2]),"status":sys.argv[3],"last":sys.argv[4]}))' \
    "$id" "$rc" "$status" "$last" >> "$jsonl"
  rm -f "$tmp"
done < "$ids_file"
echo "SUMMARY attempted=${attempted} ok=${ok} fail=${fail}" | tee -a "$out"
