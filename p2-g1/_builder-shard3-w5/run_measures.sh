#!/bin/bash
cd ~/p2-g1
for uid in AUD-0044 AUD-0047 AUD-0053 AUD-0055 AUD-0057 AUD-0064 AUD-0066 AUD-0069 AUD-0071 AUD-0072 AUD-0075 AUD-0080; do
  echo "##### MEASURE $uid $(date +%H:%M:%S)"
  PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/_measure_one_delivered.py "$uid" 2>&1
  echo "##### EXIT $uid rc=$?"
done
echo "##### ALL-DONE $(date +%H:%M:%S)"
