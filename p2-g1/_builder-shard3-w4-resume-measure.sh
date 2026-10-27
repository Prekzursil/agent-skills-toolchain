#!/usr/bin/env bash
# Run the official G-1 delivery measure for each shard3-w4 unit; log per-unit verdicts.
cd "C:/Users/Prekzursil/p2-g1" || exit 2
LOG="C:/Users/Prekzursil/p2-g1/_builder-shard3-w4-resume-measure.log"
: > "$LOG"
for id in AUD-0044 AUD-0047 AUD-0053 AUD-0055 AUD-0057 AUD-0064 AUD-0066 AUD-0069 AUD-0071 AUD-0072 AUD-0075 AUD-0080; do
  echo "===== UNIT $id =====" >> "$LOG"
  python3 -I command-center/p2-wave/_measure_one_delivered.py "$id" >> "$LOG" 2>&1
  echo "measure_rc=$? for $id" >> "$LOG"
done
echo "ALL-DONE" >> "$LOG"
