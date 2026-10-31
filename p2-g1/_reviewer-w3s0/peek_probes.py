import json, sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
root = Path(r'C:/Users/Prekzursil/p2-g1')
MY12 = ['ADV-0005','ADV-0010','ADV-0014','ADV-0015','ADV-0018','ADV-0019',
        'ADV-0022','ADV-0023','ADV-0024','ADV-0028','ADV-0029','ADV-0037']
for uid in MY12:
    pdir = root / f'command-center/p2-wave/probes/{uid}'
    print('='*70)
    print(uid, 'probe dir exists:', pdir.is_dir())
    if pdir.is_dir():
        for f in sorted(pdir.iterdir()):
            if f.is_file():
                print(f'   {f.name}  ({f.stat().st_size}B)')
        man = pdir / 'UNIT-ARTIFACT-MANIFEST.json'
        if man.is_file():
            m = json.loads(man.read_text(encoding='utf-8'))
            print('  manifest keys:', list(m.keys()))
            print('  hash_mode:', m.get('hash_mode'), '| generated_by:', m.get('generated_by'))
            for a in m.get('artifacts', []):
                print(f"   row: {a.get('path')}  {str(a.get('sha256'))[:12]}  present={a.get('present')}")
