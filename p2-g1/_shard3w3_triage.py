import json, hashlib
from pathlib import Path
BS = chr(92); CRLF = bytes([13,10]); LF = bytes([10])
REPO = Path('.')
cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
byid = {u.get('id'): u for u in (cat.get('work_units') or []) if isinstance(u, dict)}
mine = ['ARC-0055','ARC-0056','ARC-0076','AUD-0003','AUD-0005','AUD-0008','AUD-0010','AUD-0026','AUD-0032','AUD-0033','AUD-0042','AUD-0043']
NOT_DEL = {'BLOCKED','FAILED','SEVERED','TIMEOUT'}
for uid in mine:
    u = byid[uid]
    outp = str(u['output_path']).replace(BS, '/')
    out = REPO / outp
    rep = []
    if not out.is_file() or out.stat().st_size == 0:
        rep.append('ARTIFACT-ABSENT')
    else:
        try:
            text = out.read_text(encoding='utf-8'); doc = json.loads(text)
            st = str(doc.get('state','')).upper() if isinstance(doc, dict) else ''
            if st in NOT_DEL: rep.append('SELF-'+st)
            sent = u.get('completion_sentinel') or ''
            if sent and sent not in text: rep.append('SENTINEL-ABSENT')
        except Exception as e:
            rep.append('UNPARSEABLE:'+type(e).__name__)
    ret = REPO/'command-center/p2-wave/probes'/uid/'SUBAGENT-RETURN.json'
    if ret.is_file():
        try:
            rj = json.loads(ret.read_text(encoding='utf-8'))
            rs = str(rj.get('status') or rj.get('state') or '').upper()
            if rs in NOT_DEL: rep.append('RET-'+rs)
        except Exception:
            rep.append('RET-UNPARSEABLE')
    else:
        rep.append('RET-ABSENT')
    man = REPO/'command-center/p2-wave/probes'/uid/'UNIT-ARTIFACT-MANIFEST.json'
    if man.is_file():
        try:
            m = json.loads(man.read_text(encoding='utf-8'))
            rows = [a for a in (m.get('artifacts') or []) if a.get('unit_id')==uid]
            if out.is_file():
                raw = out.read_bytes().replace(CRLF, LF)
                sha = hashlib.sha256(raw).hexdigest()
                match = [a for a in rows if str(a.get('path','')).replace(BS,'/')==outp and a.get('sha256')==sha and a.get('present') is True]
                if not match:
                    rep.append('MANIFEST-SHA-MISMATCH(live_sha=%s rows=%d)' % (sha[:12], len(rows)))
        except Exception:
            rep.append('MANIFEST-UNPARSEABLE')
    else:
        rep.append('MANIFEST-ABSENT')
    rc = REPO/'command-center/receipts'/(uid+'.json')
    rcs = 'receipt:ABSENT'
    if rc.is_file():
        try:
            r = json.loads(rc.read_text(encoding='utf-8'))
            rev = r.get('reviewer') if isinstance(r.get('reviewer'), dict) else {}
            rcs = 'receipt:%s rev:%s ind:%s' % (r.get('state'), rev.get('verdict'), rev.get('independent'))
        except Exception:
            rcs = 'receipt:unparseable'
    print(uid, '|', (';'.join(rep) if rep else 'STATIC-OK'), '|', rcs)
