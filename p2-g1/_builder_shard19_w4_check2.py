import json
from pathlib import Path
mine = ['TST-0283','TST-0284','TST-0288','TST-0297','TST-0303','TST-0309','TST-0313','TST-0315','TST-0319','TST-0322','TST-0328','TST-0330']
cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
idx = {u['id']: u for u in cat['work_units']}
# dependencies resolvable?
deps = set()
for m in mine:
    deps.update(idx[m].get('dependencies') or [])
for d in sorted(deps):
    print('dep', d, 'in-catalog' if d in idx else 'NOT-IN-CATALOG')
print('---')
for uid in mine:
    r = json.loads(Path('command-center/receipts/%s.json' % uid).read_text(encoding='utf-8'))
    st = r.get('state')
    rv = r.get('reviewer') or {}
    problems = []
    if st == 'SUCCESS':
        for req in ['tests','negative_controls','reviewer','manifest_registration','downstream_consumers','residual_unknowns']:
            if req not in r: problems.append('missing:'+req)
        if len(r.get('evidence') or []) < 2: problems.append('evidence<2')
        if not str(r.get('sentinel','')).startswith('SUCCESS:'): problems.append('sentinel-not-SUCCESS')
        bad = [t for t in (r.get('tests') or []) if t.get('result') in ('FAIL','ERROR','SKIP','NOT-RUN')]
        if bad: problems.append('bad-tests:%d' % len(bad))
        nc = r.get('negative_controls') or []
        if not nc: problems.append('no-negative-controls')
        else:
            for c in nc:
                fired = c.get('fired_on_broken', c.get('fired_on_bad', c.get('fired')))
                silent = c.get('silent_on_good', c.get('silent'))
                if fired is False or silent is False: problems.append('nc-both-states-violation')
        if not (rv.get('verdict') == 'PASS' and rv.get('independent') is True):
            problems.append('reviewer-not-PASS-independent')
    mr = r.get('manifest_registration') or {}
    print('%s: state=%s reviewer=%s/%s problems=%s manifest_reg=%s' % (uid, st, rv.get('verdict'), rv.get('independent'), problems or 'NONE', (mr.get('path') or mr.get('registered') or 'n/a')))
