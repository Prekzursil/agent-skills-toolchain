import json, os, re, hashlib, subprocess, sys, time
ROOT = os.path.expanduser('~/p2-g1')
os.chdir(ROOT)
MINE = ['ADV-0127','ADV-0128','ARC-0001','ARC-0012','ARC-0013','ARC-0015','ARC-0019','ARC-0020','ARC-0021','ARC-0047','ARC-0048','ARC-0054']
def jl(p):
    with open(p, encoding='utf-8') as f: return json.load(f)
def sha_norm(path):
    with open(path,'rb') as f: b = f.read()
    return hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest()

cat = jl(os.path.join(ROOT,'command-center','WORK-UNIT-CATALOG.json'))
byid = {u['id']: u for u in cat['work_units'] if 'id' in u}
res = json.load(open(os.path.join(ROOT,'_p2-shard2-w4-review','battery_results.json'), encoding='utf-8'))

env = dict(os.environ); env['PYTHONDONTWRITEBYTECODE'] = '1'
out = {}
for uid in MINE:
    op = byid[uid]['output_path']
    pre = sha_norm(op)
    probes = []
    sr = jl(os.path.join(ROOT,'command-center','p2-wave','probes',uid,'SUBAGENT-RETURN.json'))
    probes = sr.get('named_probes') or []
    rows = []
    for p in probes:
        args = p.get('command','').split()
        # strip leading VAR=VALUE env-assignment tokens
        while args and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', args[0]):
            args = args[1:]
        if args and args[0] in ('python3','python'):
            args[0] = sys.executable
        t0 = time.time()
        try:
            cp = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, timeout=900)
            out_s = ((cp.stdout or b'') + (cp.stderr or b'')).decode('utf-8', errors='replace')
            sent = bool(re.search('SUCCESS:'+re.escape(uid), out_s))
            rows.append({'id': p.get('id'), 'exit': cp.returncode, 'dur_s': round(time.time()-t0,1),
                         'success_sentinel': sent, 'out_tail': out_s[-220:]})
        except subprocess.TimeoutExpired:
            rows.append({'id': p.get('id'), 'exit': 'TIMEOUT', 'dur_s': round(time.time()-t0,1)})
        except Exception as ex:
            rows.append({'id': p.get('id'), 'exit': 'SPAWN-ERR', 'err': str(ex)[:150], 'argv0': args[0] if args else None})
    post = sha_norm(op)
    out[uid] = {'probes': rows, 'pre_sha': pre, 'post_sha': post, 'mutated': pre != post}
    print('DONE', uid, '| exits:', [r['exit'] for r in rows], '| sentinels:', [r.get('success_sentinel') for r in rows], '| mutated:', pre != post, flush=True)

json.dump(out, open(os.path.join(ROOT,'_p2-shard2-w4-review','probe_rerun.json'),'w',encoding='utf-8'), indent=1)
print('PROBES COMPLETE')
