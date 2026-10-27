import json, hashlib
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
CATALOG = json.load(open(REPO/'command-center'/'WORK-UNIT-CATALOG.json', encoding='utf-8'))
byid = {u['id']: u for u in CATALOG['work_units']}
MINE = ['IMP-0451','IMP-0461','IMP-0465','IMP-0476','IMP-0478','IMP-0480','REL-0001','REL-0006','REL-0014','REL-0017','REL-0020','REL-0021']
BS = chr(92)
def digest(p):
    raw = Path(p).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()
for uid in MINE:
    u = byid[uid]
    out = REPO / u['output_path']
    pd = REPO/'command-center'/'p2-wave'/'probes'/uid
    row = [uid]
    if not out.is_file() or out.stat().st_size==0:
        row.append('RECEIPT-ABSENT')
    else:
        try:
            txt = out.read_text(encoding='utf-8')
            d = json.loads(txt)
            rev = d.get('reviewer') or {}
            row.append('state=%s status=%s rev=(%s,%s)' % (d.get('state'), d.get('status'), rev.get('verdict'), rev.get('independent')))
            sent = u.get('completion_sentinel') or ''
            row.append('sentinel-ok' if (not sent or sent in txt) else 'SENTINEL-MISSING')
        except Exception as e:
            row.append('RECEIPT-UNPARSEABLE:%s' % type(e).__name__)
    sr = pd/'SUBAGENT-RETURN.json'
    if sr.is_file():
        try:
            r = json.loads(sr.read_text(encoding='utf-8'))
            row.append('ret=%s' % (r.get('status') or r.get('state')))
        except Exception:
            row.append('RET-UNPARSEABLE')
    else:
        row.append('RET-ABSENT')
    man = pd/'UNIT-ARTIFACT-MANIFEST.json'
    if man.is_file():
        try:
            m = json.loads(man.read_text(encoding='utf-8'))
            rows = [a for a in (m.get('artifacts') or []) if isinstance(a,dict) and a.get('unit_id')==uid]
            if out.is_file():
                live = digest(out)
                match = [a for a in rows if str(a.get('path','')).replace(BS,'/')==u['output_path'].replace(BS,'/') and a.get('sha256')==live and a.get('present') is True]
                row.append('man-rows=%d sha=%s live=%s' % (len(rows), 'MATCH' if match else 'MISMATCH', live[:12]))
            else:
                row.append('man-rows=%d no-live' % len(rows))
        except Exception as e:
            row.append('MAN-UNPARSEABLE:%s' % type(e).__name__)
    else:
        row.append('MAN-ABSENT')
    print(' | '.join(row))
