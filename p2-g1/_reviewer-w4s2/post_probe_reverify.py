import json, hashlib, os, sys, importlib.util
os.chdir(os.path.expanduser('~/p2-g1'))
spec = importlib.util.spec_from_file_location("rsg", "platform/lib/receipt_schema_gate.py")
rsg = importlib.util.module_from_spec(spec); sys.modules['rsg']=rsg; spec.loader.exec_module(rsg)
IDS = ["ADV-0128","ARC-0001","ARC-0012","ARC-0013","ARC-0015","ARC-0019","ARC-0020","ARC-0021","ARC-0047","ARC-0048","ARC-0054"]
NOT_DELIVERING = {"BLOCKED","FAILED","SEVERED","TIMEOUT"}
def sha_lf(p):
    b=open(p,'rb').read(); return hashlib.sha256(b.replace(b'\r\n',b'\n')).hexdigest()
def sha_raw(p):
    return hashlib.sha256(open(p,'rb').read()).hexdigest()
res={}
ok_all=True
for uid in IDS:
    r = {'checks':{}}
    # artifact not-self-blocked extended scan
    op_art = json.load(open(f'command-center/receipts/{uid}.json', encoding='utf-8'))
    cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
    op = {u['id']:u for u in cat['work_units']}[uid]['output_path']
    art = json.load(open(op, encoding='utf-8'))
    bad=[]
    def scan(n):
        if isinstance(n,dict):
            for k,v in n.items():
                if k in ('state','verdict','status') and isinstance(v,str) and v.upper() in NOT_DELIVERING: bad.append(f'{k}={v}')
                scan(v)
        elif isinstance(n,list):
            for v in n: scan(v)
    scan(art)
    r['checks']['not_self_blocked'] = not bad
    if bad: r['selfblock']=bad
    # manifest rows sha (LF-normalized + raw accepted)
    man = json.load(open(f'command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json', encoding='utf-8'))
    mism=[]
    for row in man['artifacts']:
        p=row['path']
        if not os.path.exists(p): mism.append(p+':MISSING'); continue
        if row['sha256'] not in (sha_lf(p), sha_raw(p)): mism.append(f"{p}:{row['sha256'][:12]}")
    r['checks']['manifest_sha'] = not mism
    if mism: r['manifest_mismatch']=mism
    # receipt-pinned primary artifact rows: bytes + raw sha off disk (gate c3 semantics)
    rmiss=[]
    for a in op_art.get('artifacts',[]):
        if not isinstance(a,dict) or a.get('role','primary')!='primary': continue
        p=a['path']
        if not os.path.isfile(p): rmiss.append(p+':absent'); continue
        if os.path.getsize(p)!=a.get('bytes'): rmiss.append(f"{p}:bytes")
        if sha_raw(p)!=a.get('sha256'): rmiss.append(f"{p}:sha")
    r['checks']['receipt_pinned_sha'] = not rmiss
    if rmiss: r['receipt_mismatch']=rmiss
    # gate completion
    gr = rsg.evaluate_gate_a(op_art, repo_root='.').to_dict()
    r['checks']['gate_complete'] = gr['complete']
    r['blocking'] = [f"c{c['n']}:{c['outcome']}" for c in gr['conditions'] if c['outcome'] in ('UNSATISFIED','NOT-CHECKED')]
    unit_ok = r['checks']['not_self_blocked'] and r['checks']['manifest_sha'] and r['checks']['receipt_pinned_sha'] and r['checks']['gate_complete']
    r['unit_ok'] = unit_ok
    ok_all &= unit_ok
    res[uid]=r
    print(uid, 'OK' if unit_ok else f"FAIL { {k:v for k,v in r.items() if k not in ('checks','unit_ok')} }")
json.dump(res, open('_reviewer-w4s2/post_probe_reverify.json','w', encoding='utf-8'), indent=1)
print('ALL-OK' if ok_all else 'SOME-FAILED')
