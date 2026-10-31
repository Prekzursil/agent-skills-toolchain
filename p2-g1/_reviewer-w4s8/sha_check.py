import json, os, hashlib
os.chdir(os.path.expanduser('~/p2-g1'))
mine = ['IMP-0002','IMP-0006','IMP-0022','IMP-0031','IMP-0035','IMP-0036','IMP-0037','IMP-0038','IMP-0041','IMP-0044','IMP-0051','IMP-0068']
cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
byid = {u['id']: u for u in cat['work_units']}
BS = chr(92)
def sha_norm(p):
    raw = open(p,'rb').read()
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest(), ('CRLF' if b'\r\n' in raw else 'LF'), len(raw)
for uid in mine:
    op = str(byid[uid]['output_path']).replace(BS,'/')
    live, eol, rawlen = sha_norm(op)
    man = json.load(open(f'command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json', encoding='utf-8'))
    rows = man.get('artifacts') if isinstance(man, dict) else man
    if rows is None and isinstance(man, dict):
        rows = man.get('rows') or man.get('units') or []
    match = None
    if isinstance(rows, list):
        for a in rows:
            if isinstance(a, dict) and a.get('unit_id') == uid and str(a.get('path','')).replace(BS,'/') == op:
                match = a
    elif isinstance(rows, dict) and uid in rows:
        a = rows[uid]
        if str(a.get('path','')).replace(BS,'/') == op:
            match = a
    ok = bool(match) and match.get('sha256') == live and match.get('present') is True
    print(f"{uid}: manifest_sha={'MATCH' if ok else 'MISMATCH'} | live={live[:16]} eol={eol} rawbytes={rawlen}")
    if match:
        print(f"   row: sha={str(match.get('sha256'))[:16]} bytes={match.get('bytes')} present={match.get('present')}")
    else:
        print('   row: NO MATCHING ROW | manifest top keys:', list(man.keys())[:8] if isinstance(man,dict) else type(man).__name__)
    ret = json.load(open(f'command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json', encoding='utf-8'))
    print('   SUBAGENT-RETURN status:', ret.get('status'), '| ts:', ret.get('ts'))
