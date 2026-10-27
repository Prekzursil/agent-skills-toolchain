"""Census layer 3: admission-gate (schema) verdict over ALL 2007 receipts, batched."""
import json, subprocess, sys, os
from pathlib import Path

R = Path(r'C:\Users\Prekzusil\p2-g1'.replace('Prekzusil', 'Prekzursil'))
R = Path(r'C:\Users\Prekzursil\p2-g1')
PY = sys.executable
catalog = json.load(open(R / 'command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
ADMIT = R / 'command-center/receipt_validate.py'

receipt_paths = [R / u['output_path'] for u in catalog['work_units']]
accept, reject = [], []
CHUNK = 250
for i in range(0, len(receipt_paths), CHUNK):
    chunk = receipt_paths[i:i + CHUNK]
    try:
        p = subprocess.run([PY, '-I', str(ADMIT)] + [str(x) for x in chunk],
                           cwd=str(R), capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        print('chunk %d TIMEOUT' % (i // CHUNK))
        continue
    for line in (p.stdout or '').splitlines():
        line = line.strip()
        if line.startswith('ACCEPT:'):
            accept.append(line.split()[0])
        elif line.startswith('REJECT:'):
            reject.append(line.split()[0])
    err = (p.stderr or '').strip()
    if err:
        print('chunk %d stderr: %s' % (i // CHUNK, err[-200:]))

print('ACCEPT:', len(accept), '| REJECT:', len(reject), '| total:', len(accept) + len(reject))
if reject:
    print('REJECTED receipts:')
    for r in reject:
        print('  ', r)
json.dump({'accept': accept, 'reject': reject},
          open(R / '_rev_w3s10_census_schema_results.json', 'w', encoding='utf-8'), indent=1)
print('WROTE _rev_w3s10_census_schema_results.json')
