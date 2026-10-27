import json
from pathlib import Path
BS = chr(92)
REPO = Path(r'C:\Users\Prekzursil' + BS + 'p2-g1')
cat = json.load(open(REPO/'command-center'/'WORK-UNIT-CATALOG.json', encoding='utf-8'))
wu = {u['id']: u for u in cat['work_units']}
mine = ['IMP-0423','IMP-0430','IMP-0435','IMP-0437','IMP-0439','IMP-0442','IMP-0448','IMP-0450','IMP-0460','IMP-0466','IMP-0467','IMP-0468']
norm = lambda s: str(s).replace(BS, '/')
for uid in mine:
    u = wu[uid]
    out_rel = norm(u['output_path'])
    sent = str(u.get('completion_sentinel') or '')
    print('='*10, uid)
    print(' output_path:', out_rel, '| phase', u.get('phase'), '| owner_gate:', u.get('owner_approval_required'))
    p = REPO/out_rel
    if not p.is_file():
        print('  ARTIFACT MISSING'); continue
    text = p.read_text(encoding='utf-8')
    print('  artifact bytes:', p.stat().st_size)
    try:
        doc = json.loads(text)
        print('  parses OK; state:', doc.get('state'))
    except Exception as e:
        print('  PARSE FAIL:', e); doc=None
    print('  sentinel in text:', (sent in text) if sent else 'no sentinel required')
    if doc:
        arts = doc.get('artifacts') or []
        miss = []
        for a in arts:
            if isinstance(a, dict):
                ap = norm(a.get('path') or '')
                if ap and not (REPO/ap).is_file(): miss.append(ap)
        print('  receipt-listed artifacts:', len(arts), 'missing on disk:', len(miss))
        for m_ in miss: print('    MISSING:', m_)
    pd = REPO/'command-center'/'p2-wave'/'probes'/uid
    print('  probe dir exists:', pd.is_dir(), '| SUBAGENT-RETURN:', (pd/'SUBAGENT-RETURN.json').is_file(), '| MANIFEST:', (pd/'UNIT-ARTIFACT-MANIFEST.json').is_file())
    if pd.is_dir():
        print('  probe files:', sorted(x.name for x in pd.iterdir())[:12])
