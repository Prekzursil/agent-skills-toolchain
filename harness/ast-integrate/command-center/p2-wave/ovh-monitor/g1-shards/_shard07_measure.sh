#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1" || exit 1
export PYTHONDONTWRITEBYTECODE=1
OUT="/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard07_g1_measure.jsonl"
: > "$OUT"
while IFS= read -r uid; do
  [ -z "$uid" ] && continue
  echo "===== MEASURE $uid ====="
  text=$(python3 -B command-center/p2-wave/_measure_one_delivered.py "$uid" 2>&1) || true
  last=$(printf '%s\n' "$text" | awk 'NF{last=$0} END{print last}')
  ok=0
  case "$last" in
    SUCCESS:delivered\ "$uid") ok=1 ;;
  esac
  python3 - <<PY
import json
rec={"id":"$uid","ok":bool($ok),"last":"""$last"""[:300],"tail":"""${text}"""[-2500:]}
open("$OUT","a",encoding="utf-8").write(json.dumps(rec,ensure_ascii=False)+"\n")
print(rec["id"], "OK" if rec["ok"] else "FAIL", rec["last"][:160])
PY
done < /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-07.txt
echo "===== BATCH-DONE ====="
