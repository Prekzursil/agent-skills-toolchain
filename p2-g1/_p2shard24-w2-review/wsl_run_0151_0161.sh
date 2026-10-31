#!/bin/bash
set -u
cd ~/s24r2b || exit 97
export PYTHONDONTWRITEBYTECODE=1
for p in TST-0151/probe1_idle_vs_sigstop.py TST-0151/probe2_alive_before_dead.py TST-0161/probe1_conflict.py TST-0161/probe2_expiry_write.py; do
  echo "### RUN $p"
  timeout 900 python3 -B "command-center/p2-wave/probes/$p" > /tmp/out.txt 2>&1
  rc=$?
  tail -2 /tmp/out.txt
  echo "### RC=$rc for $p"
done
