import json, hashlib, sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
root = Path(r'C:/Users/Prekzursil/p2-g1')

def sha_lf(p):
    return hashlib.sha256(Path(p).read_bytes().replace(b'\r\n', b'\n')).hexdigest()

for uid in ['IMP-0430', 'TST-0174']:
    print('='*70)
    rp = root / f'command-center/receipts/{uid}.json'
    r = json.loads(rp.read_text(encoding='utf-8'))
    print(uid, 'state:', r.get('state'))
    print('reviewer:', json.dumps(r.get('reviewer'), indent=1)[:400])
    print('manifest_registration:', json.dumps(r.get('manifest_registration'), indent=1)[:300])
    man = json.loads((root / f'command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json').read_text(encoding='utf-8'))
    print('manifest top keys:', list(man.keys()))
    for a in man.get('artifacts', []):
        print('  row:', a.get('path'), a.get('sha256')[:12] if a.get('sha256') else None, 'present=', a.get('present'), 'unit_id=', a.get('unit_id'))
    # live shas
    print('  live receipt sha:', sha_lf(rp)[:12])
    cat = None
    # find catalog entry for output_path
    catall = json.loads((root/'command-center/WORK-UNIT-CATALOG.json').read_text(encoding='utf-8'))
    for u in catall['work_units']:
        if u.get('id') == uid:
            cat = u
            break
    if cat:
        op = root / cat['output_path']
        if op.is_file():
            print('  live output_path sha:', sha_lf(op)[:12], op.name)
        else:
            print('  output_path MISSING:', cat['output_path'])
