import json
from pathlib import Path
mine = ['TST-0283','TST-0284','TST-0288','TST-0297','TST-0303','TST-0309','TST-0313','TST-0315','TST-0319','TST-0322','TST-0328','TST-0330']
for uid in mine:
    r = json.loads(Path('command-center/receipts/%s.json' % uid).read_text(encoding='utf-8'))
    print('=== %s' % uid)
    print(' state=%s sentinel=%r spec_anchor=%r min_bytes=%r' % (r.get('state'), r.get('sentinel'), r.get('spec_anchor'), r.get('min_bytes_threshold')))
    print(' timestamps=%s' % json.dumps(r.get('timestamps'), ensure_ascii=False)[:200])
    print(' produced_by=%s' % json.dumps(r.get('produced_by'), ensure_ascii=False)[:200])
    print(' reviewer keys=%s' % sorted((r.get('reviewer') or {}).keys()))
    arts = r.get('artifacts') or []
    for a in arts[:6]:
        print('  art: path=%r bytes=%r role=%r keys=%s' % (str(a.get('path'))[:70], a.get('bytes'), a.get('role'), sorted(a.keys())))
    print('  n_artifacts=%d' % len(arts))
    evs = r.get('evidence') or []
    print(' evidence n=%d shapes:' % len(evs))
    for e in evs[:4]:
        print('   keys=%s' % sorted(e.keys()))
    ts = r.get('tests')
    if isinstance(ts, list):
        for t in ts[:4]:
            print('  test keys=%s result=%r' % (sorted(t.keys()) if isinstance(t,dict) else type(t).__name__, t.get('result') if isinstance(t,dict) else '-'))
    nc = r.get('negative_controls')
    if isinstance(nc, list):
        for c in nc[:3]:
            print('  nc keys=%s' % (sorted(c.keys()) if isinstance(c,dict) else type(c).__name__))
    else:
        print('  negative_controls type=%s' % type(nc).__name__)
    print(' manifest_reg=%s' % json.dumps(r.get('manifest_registration'), ensure_ascii=False)[:220])
    print(' downstream_consumers=%s residual_unknowns=%s' % (type(r.get('downstream_consumers')).__name__, type(r.get('residual_unknowns')).__name__))
