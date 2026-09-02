#!/usr/bin/env bash
# Re-run run_batch.sh until every clip has a final output, healing transient
# CUFFT_EXEC_FAILED / "CUDA error: unknown error" (big-LAMA's Fourier convs fail
# intermittently under momentary VRAM contention / WSL2 GPU-passthrough churn).
# Resumable, so each pass only retries the missing ones; a short sleep lets VRAM settle.
#   BASE=/mnt/c/.../job-root MAX=6 bash retry_until_complete.sh
set -u
: "${BASE:?set BASE=/mnt/c/.../job-root}"
SRC=${SRC:-$BASE/shorts}
OUT=${OUT:-$BASE/shorts_clean}
MAX=${MAX:-6}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
total=$(ls "$SRC"/*.mp4 2>/dev/null | wc -l)
count_done() { ls "$OUT"/*.mp4 2>/dev/null | grep -v '\.noaudio\.mp4$' | wc -l; }
for attempt in $(seq 1 "$MAX"); do
  rm -f "$OUT"/*.noaudio.mp4 2>/dev/null
  done=$(count_done)
  echo "=== retry pass $attempt/$MAX : $done/$total done ==="
  [ "$done" -ge "$total" ] && break
  BASE="$BASE" SRC="$SRC" OUT="$OUT" bash "$HERE/run_batch.sh"
  sleep 8
done
rm -f "$OUT"/*.noaudio.mp4 2>/dev/null
done=$(count_done)
echo "=== FINAL: $done/$total ==="
if [ "$done" -ge "$total" ]; then echo "SUCCESS: all $total clips cleaned"; else
  echo "FAILED: still missing ->"; for f in "$SRC"/*.mp4; do n=$(basename "$f"); [ -s "$OUT/$n" ] || echo "  $n"; done
fi
