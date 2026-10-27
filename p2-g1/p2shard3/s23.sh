#!/bin/bash
cd /home/prekzursil/p2-g1
grep -n "sorted" tools/plugin/pack.py | head -20
echo "===context==="
grep -n -B2 -A4 "unicodedata\|NFC\|normalize" tools/plugin/pack.py | head -50
echo "===census detector==="
grep -n -B3 -A25 "sorts_with_key\|key_uses_nfc" command-center/p2-wave/probes/BLD-0010/census.py | head -80
