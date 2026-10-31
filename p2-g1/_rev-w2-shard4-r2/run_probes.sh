#!/bin/bash
# Independent re-run of all 24 named probes, reviewer transport, from repo root.
cd /c/Users/Prekzursil/p2-g1 || exit 9
OUT=_rev-w2-shard4-r2/probe_rerun
mkdir -p "$OUT"
IDS="AUD-0043 AUD-0044 AUD-0047 AUD-0053 AUD-0055 AUD-0057 AUD-0064 AUD-0066 AUD-0069 AUD-0071 AUD-0072 AUD-0075"
for u in $IDS; do
  for p in command-center/p2-wave/probes/$u/probe*.py; do
    name=$(basename "$p" .py)
    log="$OUT/${u}_${name}.log"
    PYTHONDONTWRITEBYTECODE=1 python3 -B "$p" >"$log" 2>&1
    rc=$?
    echo "$u $name rc=$rc" >> "$OUT/SUMMARY.txt"
    tail -c 400 "$log" | tail -3 | sed "s/^/  [$u $name] /" >> "$OUT/SUMMARY.txt"
  done
done
echo "ALL_PROBES_DONE" >> "$OUT/SUMMARY.txt"
