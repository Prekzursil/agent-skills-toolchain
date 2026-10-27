import json, subprocess, sys, os, hashlib
from pathlib import Path
REPO = Path('.').resolve()
UNITS = ['ADV-0038','ADV-0040','ADV-0090','ADV-0091','ADV-0096','ADV-0100','ADV-0109','ADV-0110','ADV-0117','ADV-0119','ADV-0123','ADV-0124']
env = os.environ.copy(); env['PYTHONDONTWRITEBYTECODE'] = '1'
results = {}
for u in UNITS:
    row = {}
    r = subprocess.run([sys.executable, '-B', 'command-center/p2-wave/_measure_one_delivered.py', u],
                       capture_output=True, text=True, env=env, cwd=str(REPO))
    row['measure_rc'] = r.returncode
    row['measure_success'] = 'SUCCESS:delivered ' + u in ((r.stdout or '') + (r.stderr or ''))
    pdir = REPO/'command-center/p2-wave/probes'/u
    rec = json.loads((pdir/'SUBAGENT-RETURN.json').read_text(encoding='utf-8'))
    st = rec.get('state')
    row['receipt_state'] = st
    if st == 'BLOCKED':
        row['ok_contract'] = rec.get('failure', {}).get('classification') == ['reviewer-absent'] and rec.get('status') == 'DELIVERED'
    elif st == 'SUCCESS':
        rv = rec.get('reviewer') or {}
        row['ok_contract'] = rv.get('verdict') == 'PASS' and rv.get('independent') is True
    else:
        row['ok_contract'] = False
    art = json.loads((REPO/'command-center/WORK-UNIT-CATALOG.json').read_text(encoding='utf-8'))
    unit = next(x for x in art['work_units'] if x['id'] == u)
    adoc = json.loads((REPO/unit['output_path']).read_text(encoding='utf-8'))
    row['artifact_state'] = adoc.get('state')
    row['artifact_not_nondelivering'] = adoc.get('state') not in ('BLOCKED','FAILED','SEVERED','TIMEOUT')
    results[u] = row
    print(u, json.dumps(row))
json.dump(results, open('_builder_w4s0_final_sweep.json','w'), indent=1)
ok = all(r['measure_success'] and r['ok_contract'] and r['artifact_not_nondelivering'] for r in results.values())
print('ALL GREEN:', ok)
