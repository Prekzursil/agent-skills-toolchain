import json, os
base = r'C:\Users\Prekzursil\p2-g1\command-center\receipts'
mine = ['TST-0206','TST-0215','TST-0219','TST-0221','TST-0223','TST-0227','TST-0230','TST-0233']
for uid in mine:
    d = json.load(open(os.path.join(base, uid + '.json'), encoding='utf-8'))
    print('='*20, uid, '| state:', d.get('state'))
    rev = d.get('reviewer') or {}
    print(' reviewer.verdict:', rev.get('verdict'), '| independent:', rev.get('independent'), '| reviewer_id:', str(rev.get('reviewer_id'))[:80])
    defects = d.get('defects') or []
    print(' defects:', len(defects))
    for x in defects:
        print('   -', x.get('id'), x.get('severity'), x.get('status'), '|', str(x.get('summary'))[:110])
    tests = d.get('tests') or []
    bad_tests = [t for t in tests if str(t.get('result')).upper() in ('FAIL','ERROR','SKIP','NOT-RUN')]
    print(' tests:', len(tests), '| bad-result rows:', [(t.get('id'), t.get('result')) for t in bad_tests])
    ncs = d.get('negative_controls') or []
    bad_nc = [n for n in ncs if n.get('fired_on_bad_state') is False or n.get('silent_on_good_state') is False]
    kinds = [n.get('kind') for n in ncs]
    print(' negative_controls:', len(ncs), '| kinds:', kinds, '| bad-fire rows:', len(bad_nc))
    dcs = d.get('downstream_consumers') or []
    not_exec = [c for c in dcs if c.get('executed') is False or c.get('read_ok') is False]
    print(' downstream_consumers:', len(dcs), '| not-executed/not-read rows:', len(not_exec))
    for c in not_exec:
        print('   -', c.get('consumer'), 'executed=', c.get('executed'), 'read_ok=', c.get('read_ok'))
    mr = d.get('manifest_registration') or {}
    print(' manifest_registration keys:', sorted(mr.keys()), '| registered:', mr.get('registered'))
    print(' residual_unknowns:', json.dumps(d.get('residual_unknowns'))[:200])
    ev = d.get('evidence') or []
    ev_missing = [i for i, e in enumerate(ev) if not ('anchor' in e and 'probes' in e)]
    print(' evidence rows:', len(ev), '| rows missing anchor/probes:', ev_missing)
    print()
