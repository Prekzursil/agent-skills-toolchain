import json, hashlib
from pathlib import Path
BS = chr(92)
REPO = Path(r'C:\Users\Prekzursil' + BS + 'p2-g1')
def norm(p): return str(p).replace(BS, '/')
def digest(path):
    raw = Path(path).read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest()
mine = ['IMP-0430','IMP-0435','IMP-0437','IMP-0439','IMP-0442','IMP-0448','IMP-0450','IMP-0460','IMP-0466','IMP-0467','IMP-0468']
for uid in mine:
    doc = json.loads((REPO/'command-center'/'receipts'/(uid+'.json')).read_text(encoding='utf-8'))
    print('='*14, uid)
    arts = doc.get('artifacts') or []
    if not arts:
        ap = doc.get('artifact_paths') or []
        print(' artifact_paths only:', ap)
    for a in arts:
        if not isinstance(a, dict): continue
        rel = norm(a.get('path') or '')
        p = REPO/rel
        sha = str(a.get('sha256') or a.get('sha256') or '')
        if not p.is_file():
            print(f'  MISSING  {rel}  (receipt: {a.get("bytes")}B sha={sha[:12]})')
            continue
        live = digest(p)
        tag = 'SHA-OK ' if live == sha else 'SHA-DIFF'
        print(f'  {tag}  {rel}  {p.stat().st_size}B live={live[:12]} rec={sha[:12]}')
