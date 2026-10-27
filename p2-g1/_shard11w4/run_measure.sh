#!/bin/bash
cd /c/Users/Prekzursil/p2-g1
for uid in IMP-0261 IMP-0264 IMP-0269 IMP-0270 IMP-0271 IMP-0272 IMP-0273 IMP-0274 IMP-0275 IMP-0279 IMP-0303 IMP-0304; do
  echo "===== $uid ====="
  python3 command-center/p2-wave/_measure_one_delivered.py "$uid" 2>&1 | tail -6
done
