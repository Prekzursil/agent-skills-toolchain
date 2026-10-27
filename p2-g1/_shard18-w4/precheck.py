import hashlib, json
from pathlib import Path
BS = chr(92)
REPO = Path("C:/Users/Prekzursil/p2-g1")
UNITS = ['TST-0092','TST-0094','TST-0100','TST-0109','TST-0113','TST-0116','TST-0124','TST-0129','TST-0130','TST-0136','TST-0137','TST-0138']
NOT_DELIVERING = {'BLOCKED','FAILED','SEVERED','TIMEOUT'}
cat = json.load(open(REPO/'command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
cmap = {u['id']: u for u in cat['work_units'] if isinstance(u, dict) and 'id' in u}
def digest(p):
    raw = p.read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest(), len(raw)
def norm(s):
    return str(s).replace(BS, '/')
for uid in UNITS:
    unit = cmap.get(uid)
    issues = []
    out = REPO / norm(unit['output_path'])
    st = sent_ok = ret_st = sha_ok = None
    rev = ''
    try:
        text = out.read_text(encoding='utf-8')
        doc = json.loads(text)
        st = str(doc.get('state','')).upper()
        sent_ok = unit['completion_sentinel'] in text
        r = doc.get('reviewer') or {}
        rev = "rev=%s/%s" % (r.get('verdict'), r.get('independent'))
    except Exception as e:
        issues.append('artifact:%s' % type(e).__name__)
    rp = REPO / 'command-center' / 'p2-wave' / 'probes' / uid / 'SUBAGENT-RETURN.json'
    mp = REPO / 'command-center' / 'p2-wave' / 'probes' / uid / 'UNIT-ARTIFACT-MANIFEST.json'
    try:
        ret = json.loads(rp.read_text(encoding='utf-8'))
        ret_st = str(ret.get('status') or ret.get('state','')).upper()
    except Exception as e:
        issues.append('return:%s' % type(e).__name__)
    try:
        man = json.loads(mp.read_text(encoding='utf-8'))
        live_sha, nb = digest(out)
        rows = [a for a in man.get('artifacts',[]) if isinstance(a,dict) and a.get('unit_id')==uid
                and norm(a.get('path',''))==unit['output_path'] and a.get('present') is True]
        sha_ok = any(a.get('sha256')==live_sha for a in rows)
    except Exception as e:
        issues.append('manifest:%s' % type(e).__name__)
    ok = (st not in NOT_DELIVERING and st is not None and sent_ok
          and ret_st not in NOT_DELIVERING and ret_st is not None
          and sha_ok and not issues)
    flag = 'OK ' if ok else 'BAD'
    print('%s %s state=%s sentinel=%s ret=%s sha_match=%s %s %s' % (flag, uid, st, sent_ok, ret_st, sha_ok, rev, issues))
