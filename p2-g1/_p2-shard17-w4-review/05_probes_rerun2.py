import json, os, re, hashlib, subprocess, sys, time
ROOT = os.path.expanduser('~/p2-g1')
os.chdir(ROOT)

def jl(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def sha_norm(path):
    with open(path, 'rb') as f:
        b = f.read()
    return hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest()

env = dict(os.environ)
env['PYTHONDONTWRITEBYTECODE'] = '1'
env['PYTHONPATH'] = os.path.join(ROOT, '_p2-shard17-w4-review', 'shim')

out = {}
for uid, probe_rel in [('TST-0060', 'probe2_live_roundtrip.py'),
                       ('TST-0068', 'probe2_bare_sh_windows_failure.py')]:
    op = 'command-center/receipts/%s.json' % uid
    pre = sha_norm(op)
    args = [sys.executable, '-B', os.path.join(ROOT, 'command-center', 'p2-wave', 'probes', uid, probe_rel)]
    t0 = time.time()
    try:
        cp = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, timeout=900)
        out_s = ((cp.stdout or b'') + (cp.stderr or b'')).decode('utf-8', errors='replace')
        sent = bool(re.search('SUCCESS:' + re.escape(uid), out_s))
        row = {'id': 'probe2', 'exit': cp.returncode, 'dur_s': round(time.time() - t0, 1),
               'success_sentinel': sent, 'out_tail': out_s[-400:]}
    except subprocess.TimeoutExpired:
        row = {'id': 'probe2', 'exit': 'TIMEOUT', 'dur_s': round(time.time() - t0, 1)}
    post = sha_norm(op)
    out[uid] = {'probes': [row], 'pre_sha': pre, 'post_sha': post, 'mutated': pre != post}
    print('RERUN2', uid, '| exit:', row['exit'], '| sent:', row.get('success_sentinel'),
          '| mutated:', pre != post, flush=True)

with open(os.path.join(ROOT, '_p2-shard17-w4-review', 'probe_rerun2.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=1)
print('RERUN2 COMPLETE')
