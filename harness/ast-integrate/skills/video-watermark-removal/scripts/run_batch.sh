#!/usr/bin/env bash
# Batch watermark removal. Resumable: skips a clip whose output already exists.
# Parameterize via env (all have sensible defaults relative to BASE):
#   BASE  = job root (REQUIRED)         e.g. BASE=/mnt/c/Users/me/Downloads/myjob
#   SRC   = watermarked sources         (default: $BASE/shorts)
#   OUT   = cleaned output (NON-destructive) (default: $BASE/shorts_clean)
#   MASK  = per-clip masks (<clip>.png) (default: $BASE/masks)
#   CRF   = x264 quality (default 18) ; FORCE=1 re-does done clips
#   VENV  = python venv (default: ~/wm_env) ; SCRIPT = inpaint_clip.py (default: alongside this script)
set -u
: "${BASE:?set BASE=/mnt/c/.../job-root}"
SRC=${SRC:-$BASE/shorts}
OUT=${OUT:-$BASE/shorts_clean}
MASK=${MASK:-$BASE/masks}
CRF=${CRF:-18}
FORCE=${FORCE:-0}
VENV=${VENV:-$HOME/wm_env}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SCRIPT=${SCRIPT:-$HERE/inpaint_clip.py}
LOG=${LOG:-$BASE/batch.log}

source "$VENV/bin/activate"
mkdir -p "$OUT"
echo "=== batch start $(date) SRC=$SRC OUT=$OUT CRF=$CRF ===" | tee -a "$LOG"
shopt -s nullglob
clips=("$SRC"/*.mp4)
total=${#clips[@]}; i=0; ok=0; fail=0; skip=0
for f in "${clips[@]}"; do
  i=$((i+1)); name=$(basename "$f" .mp4); m="$MASK/$name.png"; o="$OUT/$name.mp4"
  if [ ! -f "$m" ]; then echo "[$i/$total] NO MASK -> SKIP $name" | tee -a "$LOG"; fail=$((fail+1)); continue; fi
  if [ "$FORCE" != "1" ] && [ -s "$o" ]; then echo "[$i/$total] exists -> skip $name" | tee -a "$LOG"; skip=$((skip+1)); continue; fi
  echo "[$i/$total] $name ..." | tee -a "$LOG"
  if python "$SCRIPT" "$f" "$m" "$o" "$CRF" >>"$LOG" 2>&1; then
    ok=$((ok+1)); tail -1 "$LOG" | sed 's/^/    /'
  else
    fail=$((fail+1)); echo "    FAILED $name (see $LOG)" | tee -a "$LOG"; rm -f "$o"
  fi
done
echo "=== batch done: ok=$ok skip=$skip fail=$fail total=$total -> $OUT ===" | tee -a "$LOG"
