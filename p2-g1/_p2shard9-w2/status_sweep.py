import json, hashlib
from pathlib import Path
REPO = Path(r"C:\Users\Prekzursil\p2-g1")
cat = json.load(open(REPO/'command-center'/'WORK-UNIT-CATALOG.json', encoding='utf-8'))
units = {u['id']: u for u in cat['work_units']}
mine = ['CNF-0169','CNF-0171','CNF-0172','CNF-0177','CNF-0184','CNF-0188','CNF-0191','CNL-0078','IMP-0002','IMP-0006','IMP-0022','IMP-0031']
ND = {'BLOCKED','FAILED','SEVERED','TIMEOUT'}
def digest(p):
    raw = p.read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest()
for uid in mine:
    u = units[uid]
    out = REPO / u['output_path']
    probs = []
    pd = REPO/'command-center'/'p2-wave'/'probes'/uid
    if not out.is_file() or out.stat().st_size <= 0:
        probs.append('artifact:absent')
    else:
        try:
            txt = out.read_text(encoding='utf-8')
            doc = json.loads(txt)
            st = str(doc.get('state','')).upper()
            sent = str(u.get('completion_sentinel') or '')
            if st in ND: probs.append(f'state:{st}')
            if sent and sent not in txt: probs.append('sentinel:absent')
        except Exception as e:
            probs.append(f'unparseable:{type(e).__name__}')
    ret = pd/'SUBAGENT-RETURN.json'; man = pd/'UNIT-ARTIFACT-MANIFEST.json'
    if not ret.is_file():
        probs.append('SUBAGENT-RETURN:absent')
    else:
        try:
            r = json.loads(ret.read_text(encoding='utf-8'))
            st = str(r.get('status') or r.get('state') or '').upper()
            if st in ND: probs.append(f'return:{st}')
            nps = r.get('named_probes') or r.get('probes') or []
            if not nps: probs.append('return:named_probes:absent')
        except Exception:
            probs.append('return:unparseable')
    if not man.is_file():
        probs.append('MANIFEST:absent')
    else:
        try:
            m = json.loads(man.read_text(encoding='utf-8'))
            rows = [a for a in (m.get('artifacts') or []) if isinstance(a,dict) and a.get('unit_id')==uid]
            if not rows:
                probs.append('manifest:row-absent')
            elif out.is_file():
                live = digest(out)
                op = u['output_path']
                match = [a for a in rows if str(a.get('path','')).replace(chr(92),'/')==op and str(a.get('sha256',''))==live and a.get('present') is True]
                if not match: probs.append('manifest:sha-mismatch')
        except Exception:
            probs.append('manifest:unparseable')
    print(uid, '::', 'OK-SHAPE' if not probs else '; '.join(probs))
