#!/usr/bin/env python3
from pathlib import Path

BODY = r"""#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$AST_INTEGRATE_ROOT" || exit 2
export PYTHONDONTWRITEBYTECODE=1
LOG="$HOME/p2-g1-shard03-measure.log"
: > "$LOG"
ok=0
fail=0
n=0
while IFS= read -r id; do
  id=${id%$'\r'}
  [ -z "$id" ] && continue
  n=$((n+1))
  echo "===== $id ($n) =====" | tee -a "$LOG"
  out=$(python3 command-center/p2-wave/_measure_one_delivered.py "$id" 2>&1)
  rc=$?
  printf '%s\n' "$out" | tee -a "$LOG"
  last=$(printf '%s\n' "$out" | tail -n 1)
  if [ "$last" = "SUCCESS:delivered $id" ]; then
    ok=$((ok+1))
    echo "OK:$id" | tee -a "$LOG"
  else
    fail=$((fail+1))
    echo "FAIL:$id $last" | tee -a "$LOG"
  fi
done < /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-03.txt
echo "SUMMARY attempted=$n ok=$ok fail=$fail" | tee -a "$LOG"
echo MEASURE-DONE | tee -a "$LOG"
"""

dest = Path(__file__).with_name("_measure_shard03.lf.sh")
dest.write_text(BODY, encoding="utf-8", newline="\n")
print(dest)
