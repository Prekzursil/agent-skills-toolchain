#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1" || exit 2
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$HOME/p2-g1/command-center/p2-wave/seed-stage:$HOME/p2-g1:$HOME/p2-g1/tools:$HOME/p2-g1/tools/measure-guard:$HOME/p2-g1/platform/lib:$HOME/p2-g1/tools/agentspec:${PYTHONPATH:-}"
OUT="$HOME/p2-g1-shard08-measure.jsonl"
: > "$OUT"
ok=0
fail=0
n=0
while IFS= read -r uid; do
  uid="${uid%$'\r'}"
  uid="${uid//$'\r'/}"
  [ -z "$uid" ] && continue
  n=$((n + 1))
  echo "===== MEASURE $uid ====="
  tmp="$(mktemp)"
  python3 -B command-center/p2-wave/_measure_one_delivered.py "$uid" >"$tmp" 2>&1
  rc=$?
  tail -n 20 "$tmp"
  last="$(grep -E '^(SUCCESS:delivered|FAILED:delivered)' "$tmp" | tail -n 1)"
  if echo "$last" | grep -q '^SUCCESS:delivered'; then
    ok=$((ok + 1))
    status=ok
  else
    fail=$((fail + 1))
    status=fail
  fi
  python3 - "$uid" "$rc" "$status" "$last" "$tmp" "$OUT" <<'PY'
import json, sys
uid, rc, status, last, tmp, out = sys.argv[1:7]
text = open(tmp, encoding="utf-8", errors="replace").read()
lines = text.splitlines()
row = {
    "id": uid,
    "rc": int(rc),
    "status": status,
    "last": last,
    "tail": lines[-16:],
}
with open(out, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(row) + "\n")
PY
  rm -f "$tmp"
done < /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-08.txt
echo "===== BATCH-DONE n=$n ok=$ok fail=$fail ====="
cp "$OUT" /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard08_measure.jsonl
echo "$n $ok $fail" > /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard08_measure.counts
