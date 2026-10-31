import json, os, subprocess, sys, glob
os.chdir(os.path.expanduser('~/p2-g1'))
REPO = os.getcwd()
mine = ['IMP-0002','IMP-0006','IMP-0022','IMP-0031','IMP-0035','IMP-0036','IMP-0037','IMP-0038','IMP-0041','IMP-0044','IMP-0051','IMP-0068']
env = os.environ.copy()
env['PYTHONDONTWRITEBYTECODE'] = '1'
env['AST_INTEGRATE_ROOT'] = REPO
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
json.dump(results, open('_reviewer-w4s8/probe_results.json','w'), indent=1)
bad = [u for u, v in results.items() if any(x.get('exit') != 0 for x in v.values()) or 'error' in v]
print()
print('PROBE BATTERY:', 'ALL 12 ALL-EXIT-0' if not bad else f'FAILURES: {bad}')
