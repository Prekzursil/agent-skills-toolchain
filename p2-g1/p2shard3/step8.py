from wslrun import wsl_bash
import json
mine = ['ADV-0005', 'AUD-0031', 'AUD-0043', 'AUD-0044', 'AUD-0055', 'AUD-0095', 'BLD-0010', 'BLD-0013', 'BLD-0014', 'BLD-0031', 'BLD-0032', 'BLD-0037', 'BLD-0044', 'BLD-0048', 'BLD-0057']
lines = ['#!/bin/bash', 'cd /home/prekzursil/p2-g1', 'export PYTHONDONTWRITEBYTECODE=1']
for uid in mine:
    lines.append(f'echo "===== MEASURE {uid} ====="')
    lines.append(f'timeout 900 python3 command-center/p2-wave/_measure_one_delivered.py {uid} 2>&1; echo "MEASURE-RC:$?"')
script = chr(10).join(lines)
open('s8.sh', 'w', newline='\n').write(script)
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s8.sh /tmp/s8.sh && bash /tmp/s8.sh', '/tmp/s8.out', timeout=7200)
if out is None:
    print('MEASURE RUN FAILED ENTIRELY')
else:
    print(out)
