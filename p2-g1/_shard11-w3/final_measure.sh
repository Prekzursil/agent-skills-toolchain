#!/bin/bash
cd ~/p2-g1
for id in IMP-0194 IMP-0195 IMP-0198 IMP-0202 IMP-0204 IMP-0207 IMP-0219 IMP-0223 IMP-0224 IMP-0228 IMP-0229 IMP-0261; do
  out=$(python3 -I command-center/p2-wave/_measure_one_delivered.py "$id" 2>&1 | tail -1)
  echo "$id -> $out"
done
