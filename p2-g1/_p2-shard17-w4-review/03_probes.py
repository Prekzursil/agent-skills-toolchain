import json, os, re, hashlib, subprocess, sys, time
ROOT = os.path.expanduser('~/p2-g1')
os.chdir(ROOT)
MINE = ['TST-0032','TST-0057','TST-0060','TST-0066','TST-0067','TST-0068',
        'TST-0070','TST-0081','TST-0085','TST-0088','TST-0090','TST-0091']

def jl(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def sha_norm(path):
    with open(path, 'rb') as f:
        b = f.read()
    return hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest()

cat = jl('command-center/WORK-UNIT-CATALOG.json')
byid = {u['id']: u for u in cat['work_units'] if isinstance(u, dict) and 'id' in u}

env = dict(os.environ)
env['PYTHONDONTWRITEBYTECODE'] = '1'
out = {}
for uid in MINE:
    op = byid[uid]['output_path']
    pre = sha_norm(op.replace('/', os.sep))
    sr = jl('command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json' % uid)
    probes = sr.get('named_probes') or []
    rows = []
    for p in probes:
        args = p.get('command', '').split()
        while args and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', args[0]):
            args = args[1:]
        if args and args[0] in ('python3', 'python'):
            args[0] = sys.executable
        t0 = time.time()
        try:
            cp = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, timeout=900)
            out_s = ((cp.stdout or b'') + (cp.stderr or b'')).decode('utf-8', errors='replace')
            sent = bool(re.search('SUCCESS:' + re.escape(uid), out_s))
            rows.append({'id': p.get('id'), 'exit': cp.returncode,
                         'dur_s': round(time.time() - t0, 1),
                         'success_sentinel': sent, 'out_tail': out_s[-260:]})
        except subprocess.TimeoutExpired:
            rows.append({'id': p.get('id'), 'exit': 'TIMEOUT', 'dur_s': round(time.time() - t0, 1)})
        except Exception as ex:
            rows.append({'id': p.get('id'), 'exit': 'SPAWN-ERR', 'err': str(ex)[:150]})
    post = sha_norm(op.replace('/', os.sep))
    out[uid] = {'probes': rows, 'pre_sha': pre, 'post_sha': post, 'mutated': pre != post}
    print('PROBES', uid, '| exits:', [r['exit'] for r in rows],
          '| sentinels:', [r.get('success_sentinel') for r in rows],
          '| mutated:', pre != post, flush=True)

with open(os.path.join(ROOT, '_p2-shard17-w4-review', 'probe_rerun.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=1)
print('PROBES COMPLETE')
