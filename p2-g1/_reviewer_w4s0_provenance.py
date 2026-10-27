import hashlib, json, sys
from pathlib import Path
def lf(p): return hashlib.sha256(Path(p).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
BS = chr(92)
man = json.loads(Path('command-center/p2-wave/probes/ADV-0037/UNIT-ARTIFACT-MANIFEST.json').read_text(encoding='utf-8'))
SRC = Path(r'C:/Users/Prekzursil/source/ast-integrate')
for a in man['artifacts']:
    rel = str(a['path']).replace(BS, '/')
    live_ok = Path(rel).is_file() and lf(rel) == a['sha256']
    src = SRC / rel
    src_ok = src.is_file() and lf(src) == a['sha256']
    tag = 'LIVE' if live_ok else ('SRC' if src_ok else 'NEITHER')
    print(f"{tag:7} | {Path(rel).name}")
# ADV-0019 receipt stale row: probe2_second_resolver.py
rec = json.loads(Path('command-center/receipts/ADV-0019.json').read_text(encoding='utf-8'))
for a in rec.get('artifacts') or []:
    rel = str(a.get('path','')).replace(BS, '/')
    if 'second_resolver' in rel:
        print('ADV-0019 receipt row:', Path(rel).name, 'rec_sha=', a['sha256'][:16],
              'live_match=', lf(rel) == a['sha256'])
        src = SRC / rel
        print('  source copy exists:', src.is_file(), 'source_match=', src.is_file() and lf(src) == a['sha256'])
man19 = json.loads(Path('command-center/p2-wave/probes/ADV-0019/UNIT-ARTIFACT-MANIFEST.json').read_text(encoding='utf-8'))
for a in man19.get('artifacts') or []:
    rel = str(a.get('path','')).replace(BS, '/')
    if 'second_resolver' in rel:
        print('ADV-0019 manifest row:', Path(rel).name, 'sha=', a['sha256'][:16],
              'live_match=', lf(rel) == a['sha256'])
