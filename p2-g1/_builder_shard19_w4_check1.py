import json, hashlib
from pathlib import Path, PurePosixPath
REPO = Path('.')
NOT_DELIVERING = {'BLOCKED','FAILED','SEVERED','TIMEOUT'}
def digest(p):
    raw = p.read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest()
def posix(s):
    return PurePosixPath(str(s).replace(chr(92), '/')).as_posix()
mine = ['TST-0283','TST-0284','TST-0288','TST-0297','TST-0303','TST-0309','TST-0313','TST-0315','TST-0319','TST-0322','TST-0328','TST-0330']
cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
idx = {u['id']: u for u in cat['work_units']}
for uid in mine:
    u = idx[uid]
    out = Path(u['output_path'])
    sentinel = u.get('completion_sentinel','')
    text = out.read_text(encoding='utf-8')
    doc = json.loads(text)
    st = str(doc.get('state','')).upper()
    man = json.load(open('command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json' % uid, encoding='utf-8'))
    rows = [a for a in (man.get('artifacts') or []) if isinstance(a,dict) and a.get('unit_id')==uid]
    live_sha = digest(out)
    match = [a for a in rows if posix(a.get('path','')) == posix(u['output_path']) and str(a.get('sha256',''))==live_sha and a.get('present') is True]
    ret = json.load(open('command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json' % uid, encoding='utf-8'))
    retst = str(ret.get('status') or ret.get('state') or '').upper()
    nprobes = len([i for i in (ret.get('named_probes') or []) if isinstance(i,dict) and i.get('command')])
    print('%s: state=%s sentinel=%s manifest-rows=%d sha-match=%s return-state=%s named-probes=%d' % (uid, st, sentinel in text, len(rows), bool(match), retst, nprobes))
