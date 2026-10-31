import json, os, subprocess, sys, glob, hashlib
os.chdir(os.path.expanduser('~/p2-g1'))
REPO = os.getcwd()
mine = ['TST-0309','TST-0313','TST-0315','TST-0319','TST-0322','TST-0328','TST-0330','TST-0332','TST-0334','TST-0335','TST-0336','TST-0337']
env = os.environ.copy()
env['PYTHONDONTWRITEBYTECODE'] = '1'
env['AST_INTEGRATE_ROOT'] = REPO
def sha_norm(p):
    raw = open(p,'rb').read()
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()
pre = {u: sha_norm(f'command-center/receipts/{u}.json') for u in mine}
results = {}
for uid in mine:
    probes = sorted(glob.glob(f'command-center/p2-wave/probes/{uid}/probe*.py'))
    if not probes:
        results[uid] = {'error': 'no probe scripts found'}
        continue
    per = {}
    for p in probes:
        try:
            r = subprocess.run([sys.executable, '-I', p], capture_output=True, text=True, timeout=300, env=env, cwd=REPO)
            per[os.path.basename(p)] = {'exit': r.returncode, 'tail': ((r.stdout or '') + (r.stderr or '')).strip()[-400:]}
        except subprocess.TimeoutExpired:
            per[os.path.basename(p)] = {'exit': 'TIMEOUT', 'tail': ''}
    results[uid] = per
    status = 'ALL-EXIT-0' if all(v.get('exit') == 0 for v in per.values()) else 'PROBE-FAILURE'
    print(f"== {uid}: {status}")
    for name, v in per.items():
        print(f"   {name}: exit={v['exit']}")
        if v['exit'] != 0:
            print('     tail:', v['tail'][-300:].replace(chr(10), ' | '))
post = {u: sha_norm(f'command-center/receipts/{u}.json') for u in mine}
mutated = [u for u in mine if pre[u] != post[u]]
json.dump({'results': results, 'pre_shas': pre, 'post_shas': post, 'mutated_by_battery': mutated},
          open('_reviewer-w4s23/probe_results.json','w'), indent=1)
bad = [u for u, v in results.items() if any(x.get('exit') != 0 for x in v.values()) or 'error' in v]
print()
print('PROBE BATTERY:', 'ALL 12 ALL-EXIT-0' if not bad else f'FAILURES: {bad}')
print('RECEIPT MUTATION BY BATTERY:', 'NONE' if not mutated else f'MUTATED: {mutated}')
