#!/bin/bash
# Sequential live measure re-runs for the 10 statically-green units.
cd ~/p2-g1 || exit 9
for uid in AUD-0082 AUD-0084 AUD-0096 BLD-0001 BLD-0002 BLD-0010 BLD-0016 BLD-0023 BLD-0024 BLD-0027 BLD-0028; do
  echo "########## MEASURE $uid ##########"
  PYTHONDONTWRITEBYTECODE=1 python3 -I command-center/p2-wave/_measure_one_delivered.py "$uid" 2>&1 | tail -25
  echo "########## rc=$? ##########"
done
echo "ALL-MEASURES-DONE"
