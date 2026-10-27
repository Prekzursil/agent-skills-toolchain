#!/usr/bin/env bash
# Detached daemon for the ProPainter v3 batch. Retries to heal transient CUDA failures;
# resumable. Launch via:
#   wsl.exe -e bash -lc 'cd <base> && setsid nohup bash pp_daemon.sh > pp_daemon.log 2>&1 < /dev/null & disown'
# Watch pp_daemon.log + pp_daemon.done with a persistent Monitor.
# Env knobs (all default to the razvan_gandu job, so a no-arg run is unchanged); exported
# env values propagate into pp_batch.sh, else pp_batch.sh falls back to the same defaults:
#   BASE   job root            (default /mnt/c/Users/Prekzursil/Downloads/razvan_gandu)
#   SRC    watermarked sources (default $BASE/shorts)
#   OUT    cleaned output      (default $BASE/shorts_clean_v2)
#   BATCH  batch script        (default $BASE/pp_batch.sh)
#   DONE   done-sentinel file  (default $BASE/pp_daemon.done)
#   MAX    max retry passes    (default 6)
set -u
BASE=${BASE:-/mnt/c/Users/Prekzursil/Downloads/razvan_gandu}
SRC=${SRC:-$BASE/shorts}; OUT=${OUT:-$BASE/shorts_clean_v2}
BATCH=${BATCH:-$BASE/pp_batch.sh}
DONE=${DONE:-$BASE/pp_daemon.done}; MAX=${MAX:-6}
rm -f "$DONE"
total=$(ls "$SRC"/*.mp4 2>/dev/null | wc -l)
cnt() { ls "$OUT"/*.mp4 2>/dev/null | wc -l; }
echo "=== pp daemon start $(date) total=$total ==="
for a in $(seq 1 "$MAX"); do
  d=$(cnt); echo "=== pp pass $a/$MAX : $d/$total ==="
  [ "$d" -ge "$total" ] && break
  bash "$BATCH"
  sleep 8
done
d=$(cnt); echo "=== pp FINAL: $d/$total ==="
echo "PP_DAEMON_EXIT d=$d/$total $(date)" > "$DONE"
