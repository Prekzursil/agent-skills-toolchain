"""w4s5 probe battery: re-run every probes/<uid>/probe*.py with python -I, exit 0 required.
Records sha of the receipt BEFORE and AFTER to detect probe-induced mutation.
"""
import glob, hashlib, json, os, subprocess, sys

os.chdir(os.path.expanduser('~/p2-g1'))
REPO = os.getcwd()
MINE = ['AUD-0084','AUD-0096','BLD-0001','BLD-0002','BLD-0010','BLD-0016',
        'BLD-0023','BLD-0024','BLD-0027','BLD-0028','BLD-0037','BLD-0042']

def sha_norm(path):
    raw = open(path,'rb').read()
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()

cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
byid = {u['id']: u for u in cat['work_units']}

env = os.environ.copy()
env['PYTHONDONTWRITEBYTECODE'] = '1'

results = {}
for uid in MINE:
    op = byid[uid]['output_path'].replace(chr(92), '/')
    sha_pre = sha_norm(op)
    probes = sorted(glob.glob('command-center/p2-wave/probes/%s/probe*.py' % uid))
    if not probes:
        results[uid] = {'error': 'no probe scripts found', 'sha_pre': sha_pre}
        print('== %s: NO PROBES' % uid)
        continue
    per = {}
    for p in probes:
        try:
            r = subprocess.run([sys.executable, '-I', p], capture_output=True, text=True,
                               timeout=600, env=env, cwd=REPO)
            per[os.path.basename(p)] = {'exit': r.returncode,
                                        'tail': ((r.stdout or '') + (r.stderr or '')).strip()[-500:]}
        except subprocess.TimeoutExpired:
            per[os.path.basename(p)] = {'exit': 'TIMEOUT', 'tail': ''}
    sha_post = sha_norm(op)
    results[uid] = {'sha_pre': sha_pre, 'sha_post': sha_post,
                    'mutated': sha_pre != sha_post, 'probes': per}
    status = 'ALL-EXIT-0' if all(v.get('exit') == 0 for v in per.values()) else 'PROBE-FAILURE'
    print('== %s: %s (mutated=%s)' % (uid, status, results[uid]['mutated']))
    for name, v in per.items():
        print('   %s: exit=%s' % (name, v['exit']))
        if v['exit'] != 0:
            print('     tail: %s' % v['tail'][-350:].replace(chr(10), ' | '))

json.dump(results, open('_reviewer-w4s5/probe_results.json', 'w'), indent=1)
bad = [u for u, v in results.items() if 'error' in v or any(x.get('exit') != 0 for x in v.get('probes', {}).values())]
mut = [u for u, v in results.items() if v.get('mutated')]
print()
print('PROBE BATTERY: %s' % ('ALL 12 ALL-EXIT-0' if not bad else 'FAILURES: %s' % bad))
print('MUTATION CHECK: %s' % ('no receipts mutated' if not mut else 'MUTATED: %s' % mut))
