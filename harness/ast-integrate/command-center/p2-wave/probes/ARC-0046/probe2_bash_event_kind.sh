#!/usr/bin/env bash
# Probe 2: bash shell, data field event_kind on replay-events.tsv.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1
python3 -B command-center/p2-wave/probes/ARC-0046/replay.py >/tmp/arc0046-probe2-replay.out
TSV="command-center/p2-wave/probes/ARC-0046/replay-events.tsv"
COST="command-center/phase3/A7/COST.json"
if [[ ! -f "$TSV" || ! -f "$COST" ]]; then
  echo "FAILED:ARC-0046-probe2 missing tsv or COST.json"
  exit 1
fi
# Different data field than probe1: event_kind, not prompt_count_after.
mapfile -t ROWS < <(awk -F '\t' 'NR>1 && ($3=="OWNER_TASK" || $3=="OWNER_PROMPT") { c[$1]++ }
END { for (k in c) print k "=" c[k] }' "$TSV" | sort)
ADD=""
EXEC=""
for row in "${ROWS[@]}"; do
  case "$row" in
    T-ADD-SKILL=*) ADD="${row#T-ADD-SKILL=}" ;;
    T-EXEC-DELETE=*) EXEC="${row#T-EXEC-DELETE=}" ;;
  esac
done
if [[ -z "$ADD" || -z "$EXEC" ]]; then
  echo "FAILED:ARC-0046-probe2 missing task counts add='$ADD' exec='$EXEC'"
  echo "rows=${ROWS[*]-}"
  exit 1
fi
python3 -B - "$COST" "$ADD" "$EXEC" <<'PY'
import json, sys
cost_path, add, exe = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
text = open(cost_path, encoding="utf-8").read()
if "SUCCESS:ARC-0046" not in text:
    print("FAILED:ARC-0046-probe2 sentinel absent")
    raise SystemExit(1)
doc = json.loads(text)
if str(doc.get("state") or "").upper() == "BLOCKED":
    print("FAILED:ARC-0046-probe2 self-declared BLOCKED")
    raise SystemExit(1)
report = doc.get("report")
body = report if isinstance(report, dict) and "task_shapes" in report else doc
got = {t["id"]: t["owner_turns"] for t in body["task_shapes"]}
live = {"T-ADD-SKILL": add, "T-EXEC-DELETE": exe}
if got != live:
    print("FAILED:ARC-0046-probe2 owner_turns mismatch live", live, "artifact", got)
    raise SystemExit(1)
py_field = {t["id"]: t["prompt_count_after"] for t in body["task_shapes"]}
if py_field != live:
    print("BLOCKED:ARC-0046 probe2 event_kind vs prompt_count_after", live, py_field)
    raise SystemExit(1)
print("bash_field=event_kind T-ADD-SKILL=%s T-EXEC-DELETE=%s" % (add, exe))
print("SUCCESS:ARC-0046-probe2 bash event_kind")
PY
