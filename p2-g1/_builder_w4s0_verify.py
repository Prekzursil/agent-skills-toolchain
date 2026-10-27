import json, subprocess, sys, hashlib
from pathlib import Path
REPO = Path('.').resolve()
UNITS = ["ADV-0038","ADV-0040","ADV-0090","ADV-0091","ADV-0096","ADV-0100","ADV-0109","ADV-0110","ADV-0117","ADV-0119","ADV-0123","ADV-0124"]
summary = {}
for u in UNITS:
    row = {}
    pdir = REPO/"command-center/p2-wave/probes"/u
    arts = list((REPO/"command-center/adversarial").glob(f"{u}-*.json"))
    row['artifact_n'] = len(arts)
    if arts:
        a = arts[0]
        try:
            doc = json.loads(a.read_text(encoding='utf-8'))
            row['artifact_state'] = doc.get('state')
            row['unit_id'] = doc.get('unit_id')
            row['bytes'] = a.stat().st_size
        except Exception as e:
            row['artifact_state'] = f'PARSE-ERROR {type(e).__name__}'
    # probes
    for p in ['probe1_delivery_predicate.py','probe2_independent_recheck.py']:
        pf = pdir/p
        if not pf.is_file():
            row[p] = 'MISSING'
            continue
        r = subprocess.run([sys.executable,'-B',str(pf)], capture_output=True, text=True, timeout=300)
        last = [l for l in (r.stdout+r.stderr).strip().splitlines() if l.startswith(('SUCCESS','FAILED'))]
        row[p] = f"exit={r.returncode} {last[-1][:80] if last else 'no-marker'}"
    # manifest sha check
    man_f = pdir/'UNIT-ARTIFACT-MANIFEST.json'
    if man_f.is_file():
        man = json.loads(man_f.read_text(encoding='utf-8'))
        prim = [x for x in man.get('artifacts',[]) if x.get('role')=='primary' or x.get('path','').find(u)>=0]
        if arts:
            live = hashlib.sha256(arts[0].read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            row['live_sha'] = live[:12]
            row['manifest_match'] = any(str(x.get('sha256'))==live for x in prim)
    # receipt state
    rec_f = pdir/'SUBAGENT-RETURN.json'
    if rec_f.is_file():
        try:
            rec = json.loads(rec_f.read_text(encoding='utf-8'))
            row['receipt_state'] = rec.get('state')
            row['receipt_class'] = (rec.get('failure') or {}).get('classification')
            row['reviewer'] = rec.get('reviewer')
        except Exception as e:
            row['receipt_state'] = f'PARSE-ERROR {type(e).__name__}'
    else:
        row['receipt_state'] = 'MISSING'
    summary[u] = row
    print(u, json.dumps(row, default=str)[:400])
json.dump(summary, open('_builder_w4s0_verify_out.json','w'), indent=1, default=str)
