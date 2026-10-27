#!/bin/bash
for u in IMP-0218 IMP-0221 IMP-0222; do
  echo "=== PROBES $u ==="
  d="command-center/p2-wave/probes/$u"
  for p in "$d"/probe1*.py "$d"/probe2*.py; do
    [ -f "$p" ] || continue
    echo "--- $p"
    PYTHONDONTWRITEBYTECODE=1 python -B "$p" 2>&1 | tail -6
    echo "rc=$?"
  done
done
