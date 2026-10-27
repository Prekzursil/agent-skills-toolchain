#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="${AST_INTEGRATE_ROOT:-$HOME/p2-g1}"
cd "$AST_INTEGRATE_ROOT" || exit 2
export PYTHONDONTWRITEBYTECODE=1
LOG="${1:-$AST_INTEGRATE_ROOT/_shard04_measure.jsonl}"
: > "$LOG"
IDS="ADV-0008 ADV-0028 ADV-0067 ADV-0087 ADV-0114 ADV-0140 ARC-0041 ARC-0082 AUD-0016 AUD-0051 AUD-0085 BLD-0026 BLD-0064 CNF-0006 CNF-0063 CNF-0101 CNF-0147 CNL-0002 CNL-0064 CNL-0107 IMP-0016 IMP-0042 IMP-0066 IMP-0086 IMP-0111 IMP-0139 IMP-0163 IMP-0201 IMP-0233 IMP-0258 IMP-0282 IMP-0307 IMP-0333 IMP-0353 IMP-0388 IMP-0417 IMP-0447 IMP-0479 RES-0033 RES-0020 RES-0150 RES-0133 SYN-0012 TST-0007 TST-0042 TST-0092 TST-0130 TST-0159 TST-0186 TST-0223 TST-0257 TST-0285 TST-0313 WFA-0005 WFA-0069 WFA-0114 WFA-0157"
n=0
ok=0
fail=0
for id in $IDS; do
  n=$((n + 1))
  echo "===== $id ($n) ====="
  tmp=$(mktemp)
  python3 -B command-center/p2-wave/_measure_one_delivered.py "$id" >"$tmp" 2>&1 || true
  cat "$tmp"
  last=$(tail -n 1 "$tmp")
  if grep -q "^SUCCESS:delivered ${id}$" "$tmp"; then
    ok=$((ok + 1))
    rec_ok=true
  else
    fail=$((fail + 1))
    rec_ok=false
  fi
  python3 -B -c 'import json,sys; from pathlib import Path; uid,ok,last,src,log=sys.argv[1],sys.argv[2]=="true",sys.argv[3],Path(sys.argv[4]),Path(sys.argv[5]); rec={"id":uid,"ok":ok,"last":last,"tail":src.read_text(encoding="utf-8",errors="replace")[-2500:]}; log.open("a",encoding="utf-8").write(json.dumps(rec,ensure_ascii=False)+"\n")' "$id" "$rec_ok" "$last" "$tmp" "$LOG"
  rm -f "$tmp"
done
echo "BATCH-DONE attempted=$n ok=$ok fail=$fail"
printf 'attempted=%s ok=%s fail=%s\n' "$n" "$ok" "$fail" > "$LOG.summary"
