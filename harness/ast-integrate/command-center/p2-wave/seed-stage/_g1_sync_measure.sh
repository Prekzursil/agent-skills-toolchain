#!/usr/bin/env bash
# Copy specific repo-relative paths (files or dirs) Windows -> mirror, then measure IDs.
# Usage: _g1_sync_measure.sh "rel/path1 rel/path2 ..." "ID1 ID2 ..." [record-wave-name]
# When a wave name is given, each measure result is appended to
# ovh-monitor/repair-claude/<wave>.jsonl and the append-only repair log.
set -uo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
MON=$SRC/command-center/p2-wave/ovh-monitor
export AST_INTEGRATE_ROOT="$DST"
export PYTHONDONTWRITEBYTECODE=1
for rel in $1; do
  if [ -d "$SRC/$rel" ]; then
    mkdir -p "$DST/$rel"
    rsync -a --exclude __pycache__ "$SRC/$rel/" "$DST/$rel/"
  elif [ -f "$SRC/$rel" ]; then
    mkdir -p "$(dirname "$DST/$rel")"
    cp -f "$SRC/$rel" "$DST/$rel"
  else
    echo "SYNC-MISSING $rel"
  fi
done
echo SYNC-OK
cd "$DST"
WAVE="${3:-}"
for id in $2; do
  out=$(python3 command-center/p2-wave/_measure_one_delivered.py "$id" 2>&1)
  last=$(printf '%s\n' "$out" | grep -v '^\s*$' | tail -1)
  printf '%s\n' "$out" | tail -25
  echo "RESULT $id :: $last"
  if [ -n "$WAVE" ]; then
    python3 - "$id" "$last" "$WAVE" <<'PY' "$out"
import json, sys
uid, last, wave, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
ok = last == f"SUCCESS:delivered {uid}"
mon = "/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor"
rec = {"id": uid, "ok": ok, "stage": "measure", "line": last[:400], "tail": out[-2500:], "src": "sync-measure"}
with open(f"{mon}/repair-claude/{wave}.jsonl", "a", encoding="utf-8") as fh:
    fh.write(json.dumps(rec) + "\n")
with open(f"{mon}/g1-repair-claude_2026-08-27.log", "a", encoding="utf-8") as fh:
    fh.write(f"{wave}\t{uid}\tmeasure\t{'OK' if ok else 'FAIL'}\t{last[:160]}\n")
PY
  fi
done
