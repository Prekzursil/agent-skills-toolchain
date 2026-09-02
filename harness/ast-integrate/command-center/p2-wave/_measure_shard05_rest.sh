#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="${AST_INTEGRATE_ROOT:-$HOME/p2-g1}"
cd "$AST_INTEGRATE_ROOT" || exit 2
export PYTHONDONTWRITEBYTECODE=1
OUT="${1:-$AST_INTEGRATE_ROOT/_g1_shard05_measure.jsonl}"
SUM="${2:-$AST_INTEGRATE_ROOT/_g1_shard05_summary.txt}"
ids=(
  ARC-0085 AUD-0018 ARC-0050 AUD-0086 BLD-0027 CC-0001 CNF-0009 CNF-0064
  CNF-0104 CNF-0145 ADV-0142 CNL-0063 CNL-0113 IMP-0018 IMP-0040 IMP-0064
  IMP-0088 IMP-0113 IMP-0138 IMP-0161 IMP-0204 IMP-0230 IMP-0259 IMP-0283
  IMP-0308 IMP-0331 IMP-0357 IMP-0396 IMP-0423 IMP-0412 IMP-0480 RES-0031
  RES-0102 RES-0149 RES-0171 SYN-0015 SYN-0037 TST-0046 SYN-0047 TST-0131
  TST-0162 TST-0193 TST-0225 TST-0258 TST-0287 TST-0314 WFA-0003 WFA-0072
  WFA-0118 WFA-0006
)
done_ids=""
if [[ -f "$OUT" ]]; then
  done_ids="$(python3 -c 'import json,sys; p=sys.argv[1]
print(" ".join(json.loads(l)["id"] for l in open(p,encoding="utf-8") if l.strip()))' "$OUT")"
fi
ok=0
fail=0
n=0
for id in "${ids[@]}"; do
  if [[ " ${done_ids} " == *" ${id} "* ]]; then
    echo "SKIP-ALREADY ${id}"
    continue
  fi
  n=$((n + 1))
  echo "==== ${id} rest(${n})"
  tmp="$(mktemp)"
  set +e
  python3 command-center/p2-wave/_measure_one_delivered.py "${id}" >"$tmp" 2>&1
  rc=$?
  set -e
  line="$(grep -E '^(SUCCESS|FAILED):delivered ' "$tmp" | tail -n 1 || true)"
  if [[ "$rc" -eq 0 && "$line" == SUCCESS:delivered* ]]; then
    ok=$((ok + 1))
    cls=SUCCESS
  else
    fail=$((fail + 1))
    cls=FAIL
  fi
  echo "${cls} rc=${rc} ${line}" | tee -a "$SUM"
  python3 - "$id" "$rc" "$line" "$tmp" "$OUT" <<'PY'
import json, sys
uid, rc, line, tmp, outp = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
text = open(tmp, encoding="utf-8", errors="replace").read()
tail_lines = [ln for ln in text.splitlines() if ln.strip()][-16:]
rec = {"id": uid, "ok": rc == 0 and line.startswith("SUCCESS:delivered"), "rc": rc, "line": line, "tail": "\n".join(tail_lines)}
with open(outp, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
PY
  rm -f "$tmp"
done
echo "REST-SUMMARY attempted=${n} ok=${ok} fail=${fail}" | tee -a "$SUM"
