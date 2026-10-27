import json, hashlib
from pathlib import Path
REPO = Path('C:/Users/Prekzursil/p2-g1')
MINE = ['IMP-0423','IMP-0430','IMP-0435','IMP-0437','IMP-0439','IMP-0442','IMP-0448','IMP-0450','IMP-0460','IMP-0466','IMP-0467','IMP-0468']
cat = json.loads((REPO/'command-center'/'WORK-UNIT-CATALOG.json').read_text(encoding='utf-8'))
wu = {u['id']: u for u in cat['work_units']}
norm = lambda s: str(s).replace(chr(92), '/')
sha_norm = lambda p: hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
for uid in MINE:
    u = wu.get(uid)
    print('='*14, uid)
    if not u:
        print('  NOT IN CATALOG'); continue
    out_rel = norm(u.get('output_path') or '')
    print('  output_path:', out_rel)
    print('  output_schema:', u.get('output_schema'))
    print('  probes:', json.dumps(u.get('probes'))[:500])
    print('  deps:', json.dumps(u.get('dependencies'))[:250])
    print('  sentinel:', u.get('completion_sentinel'), '| owner_gate:', u.get('owner_approval_required'))
    rp = REPO/out_rel if out_rel else None
    if rp and rp.is_file():
        b = rp.read_bytes()
        print('  artifact bytes:', len(b), '| live sha(CRLF-norm):', sha_norm(rp))
        try:
            doc = json.loads(b.decode('utf-8'))
            print('  parses OK; state:', doc.get('state'))
            print('  reviewer:', json.dumps(doc.get('reviewer'))[:300])
            fc = (doc.get('failure') or {}).get('classification')
            print('  failure.classification:', fc)
        except Exception as e:
            print('  PARSE FAIL:', repr(e))
    else:
        print('  ARTIFACT MISSING at', out_rel)
    pd = REPO/'command-center'/'p2-wave'/'probes'/uid
    print('  probe dir:', pd.is_dir())
    if pd.is_dir():
        for f in sorted(pd.iterdir()):
            print('    ', f.name, f.stat().st_size)
        man = pd/'UNIT-ARTIFACT-MANIFEST.json'
        if man.is_file():
            try:
                m = json.loads(man.read_text(encoding='utf-8'))
                print('  manifest:', json.dumps(m)[:800])
            except Exception as e:
                print('  MANIFEST PARSE FAIL:', repr(e))
    else:
        print('  NO PROBE DIR')
