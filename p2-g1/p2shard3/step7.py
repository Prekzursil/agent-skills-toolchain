from wslrun import wsl_bash, read_unc
import json
mine = ['ADV-0005', 'AUD-0031', 'AUD-0043', 'AUD-0044', 'AUD-0055', 'AUD-0095', 'BLD-0010', 'BLD-0013', 'BLD-0014', 'BLD-0031', 'BLD-0032', 'BLD-0037', 'BLD-0044', 'BLD-0048', 'BLD-0057']
cat = json.loads(read_unc('/home/prekzursil/p2-g1/command-center/WORK-UNIT-CATALOG.json'))
units = {u['id']: u for u in cat.get('work_units', [])}
script_lines = ['#!/bin/bash']
for uid in mine:
    op = units[uid].get('output_path', '?')
    script_lines.append(f'echo "== {uid} out={op}"')
    script_lines.append(f'ls /home/prekzursil/p2-g1/command-center/p2-wave/probes/{uid}/ 2>/dev/null | tr "\n" " "; echo')
    script_lines.append(f'test -f /home/prekzursil/p2-g1/{op} && echo ARTIFACT-EXISTS || echo ARTIFACT-ABSENT')
    script_lines.append(f'test -s /home/prekzursil/p2-g1/{op} && echo ARTIFACT-NONEMPTY || true')
script = chr(10).join(script_lines)
open('s7.sh', 'w', newline='\n').write(script)
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s7.sh /tmp/s7.sh && bash /tmp/s7.sh', '/tmp/s7.out', timeout=600)
print(out if out else 'FAILED')
