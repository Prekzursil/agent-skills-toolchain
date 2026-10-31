import hashlib, json
from pathlib import Path
BS = chr(92)
def norm(p):
    return p.replace(BS, '/')
def digest(p):
    raw = p.read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest()
REPO = Path.home() / 'p2-g1'
NOT_DELIVERING = {'BLOCKED','FAILED','SEVERED','TIMEOUT'}
ids = ['AUD-0082','AUD-0084','AUD-0095','AUD-0096','BLD-0001','BLD-0002','BLD-0010','BLD-0016','BLD-0023','BLD-0024','BLD-0027','BLD-0028']
cat = json.loads((REPO/'command-center/WORK-UNIT-CATALOG.json').read_text(encoding='utf-8'))
wus = {u['id']: u for u in cat['work_units']}
for uid in ids:
    unit = wus[uid]
    out_rel = norm(unit['output_path'])
    out = REPO / out_rel
    prob = REPO/'command-center/p2-wave/probes'/uid
    issues = []
    if not out.is_file() or out.stat().st_size <= 0:
        issues.append('artifact-absent')
    else:
        try:
            text = out.read_text(encoding='utf-8'); doc = json.loads(text)
        except Exception as e:
            issues.append('unparseable:'+type(e).__name__)
        else:
            st = str(doc.get('state','')).upper() if isinstance(doc,dict) else ''
            if st in NOT_DELIVERING: issues.append('self-declared:'+st)
            sentinel = unit.get('completion_sentinel','')
            if sentinel and sentinel not in text: issues.append('sentinel-absent')
    rp = prob/'SUBAGENT-RETURN.json'
    if not rp.is_file():
        issues.append('subagent-return-absent')
    else:
        try: ret = json.loads(rp.read_text(encoding='utf-8'))
        except Exception: issues.append('return-unparseable')
        else:
            sr = str(ret.get('status') or ret.get('state') or '').upper()
            if sr in NOT_DELIVERING: issues.append('return:'+sr)
    mp = prob/'UNIT-ARTIFACT-MANIFEST.json'
    if not mp.is_file():
        issues.append('manifest-absent')
    else:
        try: man = json.loads(mp.read_text(encoding='utf-8'))
        except Exception: issues.append('manifest-unparseable')
        else:
            rows = [a for a in (man.get('artifacts') or []) if isinstance(a,dict) and a.get('unit_id')==uid]
            if not rows: issues.append('manifest-row-absent')
            else:
                live = digest(out)
                match = [a for a in rows if norm(str(a.get('path','')))==out_rel and str(a.get('sha256',''))==live and a.get('present') is True]
                if not match: issues.append('manifest-sha-mismatch')
    rstate = None; rrev = None
    rp2 = REPO/'command-center/receipts'/(uid+'.json')
    cands = [rp2, out] if uid.startswith('AUD') else [out]
    for cand in cands:
        if cand.is_file():
            try:
                rd = json.loads(cand.read_text(encoding='utf-8'))
                if isinstance(rd,dict) and rd.get('state'):
                    rstate = rd.get('state'); rrev = rd.get('reviewer'); break
            except Exception: pass
    print(uid + ': ' + ('GREEN-STATIC' if not issues else str(issues)) + ' | receipt-state=' + str(rstate) + ' | reviewer=' + (str(rrev.get('verdict'))+'/'+str(rrev.get('independent')) if isinstance(rrev,dict) else str(rrev)))
