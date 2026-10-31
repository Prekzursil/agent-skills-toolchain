import json, hashlib, os
ids = ['AUD-0044','AUD-0047','AUD-0053','AUD-0055','AUD-0057','AUD-0064','AUD-0066','AUD-0069','AUD-0071','AUD-0072','AUD-0075','AUD-0080']
data = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
units = {u['id']: u for u in data.get('work_units', []) if isinstance(u, dict)}
def sha(p):
    raw = open(p,'rb').read().replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest()
NOT = {'BLOCKED','FAILED','SEVERED','TIMEOUT'}
BS = chr(92)
for i in ids:
    u = units[i]
    out = u['output_path'].replace(BS+BS, '/')
    st = {}
    try:
        doc = json.load(open(out, encoding='utf-8'))
        st['parses'] = True
        st['state'] = doc.get('state') if isinstance(doc, dict) else '?'
        st['selfdecl'] = str(doc.get('state','')).upper() in NOT if isinstance(doc, dict) else False
    except Exception as e:
        st['parses'] = False; st['err'] = type(e).__name__
    st['sentinel'] = u.get('completion_sentinel','') in open(out, encoding='utf-8', errors='ignore').read()
    pd = 'command-center/p2-wave/probes/' + i
    files = sorted(os.listdir(pd)) if os.path.isdir(pd) else []
    st['probe_files'] = files
    srp = os.path.join(pd,'SUBAGENT-RETURN.json')
    if os.path.isfile(srp):
        try:
            sr = json.load(open(srp, encoding='utf-8'))
            st['sr_status'] = sr.get('status') or sr.get('state')
            st['sr_notdeliv'] = str(sr.get('status') or sr.get('state') or '').upper() in NOT
        except Exception:
            st['sr_status'] = 'UNPARSEABLE'
    mp = os.path.join(pd,'UNIT-ARTIFACT-MANIFEST.json')
    if os.path.isfile(mp):
        try:
            man = json.load(open(mp, encoding='utf-8'))
            rows = [a for a in (man.get('artifacts') or []) if isinstance(a,dict) and a.get('unit_id')==i]
            live = sha(out)
            m = [a for a in rows if str(a.get('path','')).replace(BS+BS,'/')==out and a.get('sha256')==live and a.get('present') is True]
            st['man_rows'] = len(rows); st['man_match'] = bool(m)
        except Exception as e:
            st['man_err'] = type(e).__name__
    print(i, json.dumps(st)[:500])
