import json, os, sys, re, subprocess, hashlib
from jsonschema import Draft202012Validator, RefResolver
BASE = os.path.expanduser('~')
P2 = os.path.join(BASE, 'p2-g1')
OUT = os.path.join(P2, '_rev-w2-shard9-battery')
FULL = os.path.join(OUT, 'full_probe_outputs')
os.makedirs(FULL, exist_ok=True)
IDS = ['CNF-0169','CNF-0171','CNF-0172','CNF-0177','CNF-0184','CNF-0188','CNF-0191','CNL-0078','IMP-0002','IMP-0006','IMP-0022','IMP-0031']
cat = json.load(open(os.path.join(P2,'command-center','WORK-UNIT-CATALOG.json'), encoding='utf-8'))
byid = {e['id']: e for e in cat['work_units']}
env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
pat = re.compile(r'\b(BLOCKED|NOT-DELIVERED|Traceback|sentinel-mismatch)\b', re.I)

summary = {}
for u in IDS:
    e = byid[u]
    d = os.path.join(P2,'command-center','p2-wave','probes',u)
    scripts = sorted(f for f in os.listdir(d) if f.startswith('probe') and f.endswith('.py'))
    # full-output probe rerun
    probe_ok, marker_hits = True, []
    for sc in scripts:
        try:
            r = subprocess.run([sys.executable, '-I', os.path.join(d, sc)], cwd=P2, env=env,
                               capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            probe_ok = False; marker_hits.append(sc+':TIMEOUT'); continue
        blob = (r.stdout or '') + '||STDERR||' + (r.stderr or '')
        open(os.path.join(FULL, f'{u}__{sc}.out'), 'w', encoding='utf-8').write(f'EXIT={r.returncode}\n'+blob)
        if r.returncode != 0:
            probe_ok = False; marker_hits.append(f'{sc}:exit{r.returncode}')
        for line in blob.splitlines():
            if pat.search(line) and 'SUCCESS:' not in line:
                marker_hits.append(f'{sc}:{line.strip()[:160]}')
    # artifact + schema validation
    art_path = os.path.join(P2, e['output_path'].replace('/', os.sep))
    art = json.load(open(art_path, encoding='utf-8'))
    schema_field = e['output_schema']
    primary = schema_field.split(' + ')[0].strip()
    sp = os.path.join(P2, primary.replace('/', os.sep))
    schema = json.load(open(sp, encoding='utf-8'))
    resolver = RefResolver(base_uri='file:///' + os.path.abspath(sp).replace(os.sep, '/').lstrip('/'), referrer=schema)
    v = Draft202012Validator(schema, resolver=resolver)
    errs = sorted(v.iter_errors(art), key=lambda x: list(x.path))
    err_txt = [f'{list(er.path)}: {er.message[:150]}' for er in errs[:8]]
    # receipt_core rule: SUCCESS requires reviewer PASS + independent
    rv = art.get('reviewer') or {}
    core_ok = (art.get('state') != 'SUCCESS') or (rv.get('verdict') == 'PASS' and rv.get('independent') is True)
    # deep self-block scan
    raw = open(art_path, encoding='utf-8').read()
    selfblock = re.findall(r'"state"\s*:\s*"(BLOCKED|FAILED)"', raw) + re.findall(r'"verdict"\s*:\s*"(BLOCKED|FAILED)"', raw)
    summary[u] = {
        'probes_full_exit0': probe_ok, 'probe_markers': marker_hits[:6],
        'schema_file': primary, 'schema_errors': len(errs), 'schema_err_sample': err_txt,
        'receipt_core_ok': core_ok,
        'selfblock_hits': selfblock[:5],
        'state': art.get('state'), 'reviewer_verdict': rv.get('verdict'), 'reviewer_independent': rv.get('independent'),
    }
json.dump(summary, open(os.path.join(OUT,'battery2_out.json'),'w',encoding='utf-8'), indent=1)
for u in IDS:
    s = summary[u]
    print(u, '| probes0:', s['probes_full_exit0'], '| schema_errs:', s['schema_errors'],
          '| core_ok:', s['receipt_core_ok'], '| selfblock:', s['selfblock_hits'],
          '| markers:', s['probe_markers'] if s['probe_markers'] else 'none')
    if s['schema_errors']: print('   ', s['schema_err_sample'])
