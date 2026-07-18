#!/usr/bin/env bash
# ProPainter per-frame watermark removal batch (v3 pipeline). Resumable: skips clips whose
# v2 output already exists. Writes to shorts_clean_v2/ (non-destructive; shorts_clean/ kept).
# Env knobs (all default to the razvan_gandu job, so a no-arg run is unchanged):
#   BASE     job root            (default /mnt/c/Users/Prekzursil/Downloads/razvan_gandu)
#   SRC      watermarked sources (default $BASE/shorts)
#   OUT      cleaned output, NON-destructive (default $BASE/shorts_clean_v2)
#   PIPELINE per-clip script      (default $BASE/propaint_pipeline.py)
#   VENV     python venv          (default ~/wm_env)
#   LOG      log file             (default $BASE/pp_batch.log)
set -u
BASE=${BASE:-/mnt/c/Users/Prekzursil/Downloads/razvan_gandu}
SRC=${SRC:-$BASE/shorts}
OUT=${OUT:-$BASE/shorts_clean_v2}
PIPELINE=${PIPELINE:-$BASE/propaint_pipeline.py}
VENV=${VENV:-$HOME/wm_env}
LOG=${LOG:-$BASE/pp_batch.log}
source "$VENV/bin/activate"
mkdir -p "$OUT"
echo "=== pp batch start $(date) ===" | tee -a "$LOG"
shopt -s nullglob
clips=("$SRC"/*.mp4); total=${#clips[@]}; i=0; ok=0; fail=0; skip=0
for f in "${clips[@]}"; do
  i=$((i+1)); name=$(basename "$f" .mp4); o="$OUT/$name.mp4"
  if [ -s "$o" ]; then echo "[$i/$total] exists -> skip $name" | tee -a "$LOG"; skip=$((skip+1)); continue; fi
  echo "[$i/$total] $name ..." | tee -a "$LOG"
  if python "$PIPELINE" "$f" "$o" >>"$LOG" 2>&1; then
    ok=$((ok+1)); grep -E "^(DONE|NO-LOGO)" "$LOG" | tail -1 | sed 's/^/    /'
  else
    fail=$((fail+1)); echo "    FAILED $name (see $LOG)" | tee -a "$LOG"; rm -f "$o"
  fi
done
echo "=== pp batch done: ok=$ok skip=$skip fail=$fail total=$total ===" | tee -a "$LOG"
