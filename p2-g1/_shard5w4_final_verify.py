import json, hashlib, os, subprocess, sys
BS = chr(92)
ids=['BLD-0059','CC-0009','CC-0010','CC-0012','CC-0019','CNF-0077','CNF-0132','CNF-0133','CNF-0136','CNF-0147','CNF-0149','CNF-0152']
cat=json.load(open('command-center/WORK-UNIT-CATALOG.json',encoding='utf-8'))
byid={u['id']:u for u in cat['work_units'] if isinstance(u,dict)}
for uid in ids:
    e=byid[uid]
    outp=e['output_path'].replace(BS,'/')
    raw=open(outp,'rb').read(); live=hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()
    art=json.load(open(outp,encoding='utf-8'))
    man=json.load(open('command-center/p2-wave/probes/'+uid+'/UNIT-ARTIFACT-MANIFEST.json',encoding='utf-8'))
    rows=[a for a in man.get('artifacts',[]) if a.get('unit_id')==uid and str(a.get('path','')).replace(BS,'/')==outp and a.get('sha256')==live and a.get('present') is True]
    sent=e.get('completion_sentinel','') or ''
    txt_ok = (sent in raw.decode('utf-8',errors='ignore')) if sent else None
    rp='command-center/receipts/'+uid+'.json'
    rec=json.load(open(rp,encoding='utf-8')) if os.path.isfile(rp) else None
    p=subprocess.run([sys.executable,'-B','command-center/p2-wave/_measure_one_delivered.py',uid],capture_output=True,text=True)
    last=(p.stdout.strip().splitlines() or [''])[-1]
    rv=art.get('reviewer') or {}
    row=dict(uid=uid, measure_last=last, bytes=len(raw), sha12=live[:12],
             manifest_row_match=bool(rows), sentinel_ok=txt_ok,
             art_state=art.get('state'), rv_verdict=rv.get('verdict'), rv_independent=rv.get('independent'),
             owner_gated=e.get('owner_approval_required'),
             receipt_state=(rec or {}).get('state'),
             receipt_verdict=((rec or {}).get('reviewer') or {}).get('verdict'))
    print(json.dumps(row))
