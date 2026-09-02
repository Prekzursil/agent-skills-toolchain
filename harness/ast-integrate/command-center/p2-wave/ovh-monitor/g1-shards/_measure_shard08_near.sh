#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT=/home/prekzursil/p2-g1
cd /home/prekzursil/p2-g1 || exit 2
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="/home/prekzursil/p2-g1/command-center/p2-wave/seed-stage:/home/prekzursil/p2-g1:/home/prekzursil/p2-g1/tools:/home/prekzursil/p2-g1/tools/measure-guard:/home/prekzursil/p2-g1/platform/lib:/home/prekzursil/p2-g1/tools/agentspec:${PYTHONPATH:-}"
OUT=/home/prekzursil/p2-g1-shard08-near.jsonl
: > "$OUT"
ok=0
fail=0
n=0
for uid in WFA-0121 TST-0230 TST-0199 CC-0003 IMP-0167 IMP-0334 IMP-0359 IMP-0420 ADV-0009 TST-0018 IMP-0051; do
  n=$((n + 1))
  echo "===== MEASURE $uid ====="
  tmp="$(mktemp)"
  python3 -B command-center/p2-wave/_measure_one_delivered.py "$uid" >"$tmp" 2>&1
  rc=$?
  tail -n 12 "$tmp"
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
row = {"id": uid, "rc": int(rc), "status": status, "last": last, "tail": text.splitlines()[-12:]}
with open(out, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(row) + "\n")
PY
  rm -f "$tmp"
done
echo "===== NEAR-DONE n=$n ok=$ok fail=$fail ====="
cp "$OUT" /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard08_near.jsonl
echo "$n $ok $fail" > /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard08_near.counts
