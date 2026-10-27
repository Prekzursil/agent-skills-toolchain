import json, os, sys, shutil, hashlib, subprocess, time
BASE = os.path.expanduser('~')
P2 = os.path.join(BASE, 'p2-g1')
OUT = os.path.join(P2, '_rev-w2-shard9-battery')
BKS = os.path.join(OUT, 'backups')
os.makedirs(BKS, exist_ok=True)
IDS = ['CNF-0169','CNF-0171','CNF-0172','CNF-0177','CNF-0184','CNF-0188','CNF-0191','CNL-0078','IMP-0002','IMP-0006','IMP-0022','IMP-0031']

cat = json.load(open(os.path.join(P2,'command-center','WORK-UNIT-CATALOG.json'), encoding='utf-8'))
byid = {e['id']: e for e in cat['work_units']}

def lf_sha(p):
    b = open(p,'rb').read()
    return hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest(), len(b)

report = {}
# 1. backup receipts byte-exact
for u in IDS:
    ap = os.path.join(P2, byid[u]['output_path'].replace('/', os.sep))
    dst = os.path.join(BKS, u + '.json')
    shutil.copy2(ap, dst)

# 2. run probes
env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
results = {}
for u in IDS:
    d = os.path.join(P2,'command-center','p2-wave','probes',u)
    scripts = sorted(f for f in os.listdir(d) if f.startswith('probe') and f.endswith('.py'))
    for sc in scripts:
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, '-I', os.path.join(d, sc)], cwd=P2, env=env,
                               capture_output=True, text=True, timeout=300)
            code, tail = r.returncode, (r.stdout[-400:] + '|' + r.stderr[-400:])
        except subprocess.TimeoutExpired:
            code, tail = 'TIMEOUT', ''
        dt = round(time.time()-t0, 1)
        results.setdefault(u, []).append({'script': sc, 'exit': code, 'secs': dt, 'tail': tail.replace('\n',' ')[-260:]})

# 3. post-run hash recheck vs pre-run backup and manifest
for u in IDS:
    ap = os.path.join(P2, byid[u]['output_path'].replace('/', os.sep))
    post_sha, post_n = lf_sha(ap)
    pre_sha, pre_n = lf_sha(os.path.join(BKS, u + '.json'))
    mfp = os.path.join(P2,'command-center','p2-wave','probes',u,'UNIT-ARTIFACT-MANIFEST.json')
    mf = json.load(open(mfp, encoding='utf-8'))
    op = byid[u]['output_path']
    rows = [r for r in mf.get('artifacts',[]) if r.get('path')==op] or mf.get('artifacts',[])
    row = rows[0] if rows else {}
    report[u] = {
        'probe_runs': results.get(u, []),
        'all_probes_exit0': all(r['exit']==0 for r in results.get(u, [])),
        'artifact_changed_by_probes': post_sha != pre_sha,
        'post_run_lf_sha': post_sha, 'pre_run_lf_sha': pre_sha,
        'manifest_sha': row.get('sha256'),
        'manifest_match_post': post_sha == row.get('sha256'),
        'manifest_match_pre': pre_sha == row.get('sha256'),
    }

json.dump(report, open(os.path.join(OUT,'battery1_out.json'),'w',encoding='utf-8'), indent=1)
for u in IDS:
    r = report[u]
    print(u, '| probes_exit0:', r['all_probes_exit0'], '| mutated:', r['artifact_changed_by_probes'],
          '| mf_pre:', r['manifest_match_pre'], '| mf_post:', r['manifest_match_post'])
    for pr in r['probe_runs']:
        print('   ', pr['script'], 'exit=', pr['exit'], 'secs=', pr['secs'])
        if pr['exit'] != 0: print('     TAIL:', pr['tail'])
