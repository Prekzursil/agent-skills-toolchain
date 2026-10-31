import json, os, datetime
from pathlib import Path
mine = ['TST-0283','TST-0284','TST-0288','TST-0297','TST-0303','TST-0309','TST-0313','TST-0315','TST-0319','TST-0322','TST-0328','TST-0330']
def iso(mtime):
    return datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
for uid in mine:
    r = json.loads(Path('command-center/receipts/%s.json' % uid).read_text(encoding='utf-8'))
    print('=== %s' % uid)
    rv = r.get('reviewer') or {}
    print(' reviewer_id=%r verdict=%r independent=%r reviewed_at=%r' % (rv.get('reviewer_id'), rv.get('verdict'), rv.get('independent'), rv.get('reviewed_at')))
    print(' defects=%s' % json.dumps(r.get('defects'), ensure_ascii=False)[:200])
    arts = r.get('artifacts') or []
    print(' n_artifacts=%d' % len(arts))
    for a in arts:
        p = a.get('path')
        ex = Path(p).exists() if p else False
        sz = Path(p).stat().st_size if ex else -1
        print('   path=%s exists=%s live_size=%d recorded_bytes=%r role=%r' % (str(p)[:80], ex, sz, a.get('bytes'), a.get('role')))
    # evidence length
    ev = r.get('evidence')
    if isinstance(ev, list): print(' evidence LIST n=%d' % len(ev))
    elif isinstance(ev, dict): print(' evidence DICT keys=%s' % list(ev.keys()))
    # residual-ish keys
    for k in ['residual_unknowns','residuals','unknowns','open_questions','limitations','notes']:
        if k in r and r[k]:
            print(' %s: %s' % (k, json.dumps(r[k], ensure_ascii=False)[:220]))
    # probe file mtimes for timestamp derivation
    pd = Path('command-center/p2-wave/probes/%s' % uid)

