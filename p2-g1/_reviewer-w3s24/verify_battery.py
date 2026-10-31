import json, os, subprocess, sys, hashlib
BS = chr(92)
repo = r'C:\Users\Prekzursil\p2-g1'
mine = ['TST-0206','TST-0215','TST-0219','TST-0221','TST-0223','TST-0227','TST-0230','TST-0233']
results = {}
for uid in mine:
    row = {}
    rpath = os.path.join(repo, 'command-center', 'receipts', uid + '.json')
    raw = open(rpath, 'rb').read()
    lf = raw.replace(b'\r\n'.replace(b'\r', chr(13).encode()), b'\n') if False else raw.replace(b'\r\n', b'\n')
    row['sha256_LF'] = hashlib.sha256(lf).hexdigest()
    row['raw_bytes'] = len(raw)
    man = json.load(open(os.path.join(repo, 'command-center', 'p2-wave', 'probes', uid, 'UNIT-ARTIFACT-MANIFEST.json'), encoding='utf-8'))
    want = 'command-center/receipts/' + uid + '.json'
    match = [a for a in man.get('artifacts', [])
             if a.get('unit_id') == uid and str(a.get('path','')).replace(BS, '/') == want
             and a.get('sha256') == row['sha256_LF'] and a.get('present') is True]
    row['manifest_sha_match'] = bool(match)
    d = json.loads(raw.decode('utf-8'))
    rev = d.get('reviewer') or {}
    row['state'] = d.get('state')
    row['failure_absent'] = d.get('failure') is None
    row['reviewer_verdict'] = rev.get('verdict')
    row['reviewer_independent'] = rev.get('independent')
    row['sentinel'] = str(d.get('sentinel'))[:40]
    row['closure_valid'] = (d.get('state') == 'SUCCESS' and d.get('failure') is None
                            and rev.get('verdict') == 'PASS' and rev.get('independent') is True)
    probes = sorted(os.listdir(os.path.join(repo, 'command-center', 'p2-wave', 'probes', uid)))
    pyfiles = [p for p in probes if p.startswith('probe') and p.endswith('.py')]
    rcs = []
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['AST_INTEGRATE_ROOT'] = repo
    for p in pyfiles:
        pr = subprocess.run([sys.executable, '-B', os.path.join('command-center','p2-wave','probes',uid,p)],
                            cwd=repo, capture_output=True, text=True, timeout=2700, env=env)
        rcs.append((p, pr.returncode))
    row['direct_probe_rcs'] = rcs
    row['all_probes_zero'] = all(rc == 0 for _, rc in rcs)
    results[uid] = row
    print(uid, '| sha_match:', row['manifest_sha_match'], '| state:', row['state'],
          '| reviewer:', row['reviewer_verdict'], '/', row['reviewer_independent'],
          '| probes:', rcs, '| closure_valid:', row['closure_valid'])
json.dump(results, open(r'C:\Users\Prekzursil\.claude\temp_w3s24_battery.json','w'), indent=1)
print()
bad = [u for u,r in results.items() if not (r['manifest_sha_match'] and r['all_probes_zero'] and r['closure_valid'] and r['failure_absent'])]
print('UNITS WITH ANY HARD-CHECK FAILURE:', bad or 'none')
