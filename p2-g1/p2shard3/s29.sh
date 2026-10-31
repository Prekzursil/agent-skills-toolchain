#!/bin/bash
cd /home/prekzursil/p2-g1/command-center/p2-wave/probes/BLD-0057
grep -n -A30 "def spawn" ramp.py | head -45
echo "===guard threshold==="
grep -n -B3 -A15 "abort\|ratio" guard.py | head -60
echo "===live snapshot==="
python3 -c "
import observe as O, json
s = O.snapshot()
print(json.dumps({k: s.get(k) for k in ('commit_limit_bytes','committed_as_bytes','commit_ratio','process_count','mem_total_bytes','ram_used_ratio')}, indent=1))
"
