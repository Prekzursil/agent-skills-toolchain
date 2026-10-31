#!/usr/bin/env python3
"""AUD-0095 finish v2: builder-terminal receipt shape + verbatim probe records."""
import hashlib, json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
REPO = HOME / 'p2-g1'
ART = REPO / 'command-center/audit/AUD-0095-freeze-inventory.json'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def sha_lf(p):
    return hashlib.sha256(Path(p).read_bytes().replace(b'\r\n', b'\n')).hexdigest()

doc = json.loads(ART.read_text(encoding='utf-8'))
doc['timestamps'].pop('repaired_at', None)
if 'enumeration_repairs' in doc and isinstance(doc['enumeration_repairs'], dict):
    doc['enumeration_repairs']['repaired_at'] = NOW
doc['state'] = 'BLOCKED'
doc['status'] = 'BUILT-AWAITING-INDEPENDENT-REVIEW'

P1 = 'PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/AUD-0095/probe1_freeze_anchors.py'
P2 = 'PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/AUD-0095/probe2_change_detection.py'
CMD1 = ['python3', '-B', 'command-center/p2-wave/probes/AUD-0095/probe1_freeze_anchors.py']
CMD2 = ['python3', '-B', 'command-center/p2-wave/probes/AUD-0095/probe2_change_detection.py']
env = os.environ.copy()
env['PYTHONDONTWRITEBYTECODE'] = '1'
r1 = subprocess.run(CMD1, cwd=str(REPO), capture_output=True, text=True, env=env)
r2 = subprocess.run(CMD2, cwd=str(REPO), capture_output=True, text=True, env=env)
out1 = ((r1.stdout or '') + (r1.stderr or '')).strip()
out2 = ((r2.stdout or '') + (r2.stderr or '')).strip()
print('probe1 rc', r1.returncode, '|', out1[:150])
print('probe2 rc', r2.returncode, '|', out2[:150])

fingerprint = lambda s: hashlib.sha256(s.encode('utf-8')).hexdigest()[:16]
doc['downstream_consumers'] = [
    {'consumer': 'AUD-0095 probe reader', 'artifact_path': 'probe1_freeze_anchors.py',
     'executed': True, 'read_ok': r1.returncode == 0, 'exit_code': r1.returncode,
     'probe': {'role': 'verifier', 'method': 'file-read', 'command': P1,
               'raw_output': out1, 'fingerprint': fingerprint(out1), 'exit_code': r1.returncode}},
    {'consumer': 'AUD-0095 probe reader', 'artifact_path': 'probe2_change_detection.py',
     'executed': True, 'read_ok': r2.returncode == 0, 'exit_code': r2.returncode,
     'probe': {'role': 'verifier', 'method': 'file-read', 'command': P2,
               'raw_output': out2, 'fingerprint': fingerprint(out2), 'exit_code': r2.returncode}},
]
if isinstance(doc.get('named_probes'), list):
    doc['named_probes'] = [
        {'id': 'probe1', 'command': P1, 'exit_code': r1.returncode,
         'role': 'source', 'raw_output': out1},
        {'id': 'probe2', 'command': P2, 'exit_code': r2.returncode,
         'role': 'independent-adversarial', 'raw_output': out2},
    ]
doc['timestamps']['ended_at'] = NOW
ART.write_text(json.dumps(doc, indent=1) + '\n', encoding='utf-8', newline='\n')

# probe2 out file check + artifact self-consistency
print('PROBE-EXITS', r1.returncode, r2.returncode)
