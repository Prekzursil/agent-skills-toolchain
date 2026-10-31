import json, os, re, hashlib, subprocess, sys, time
ROOT = os.path.expanduser('~/p2-g1')
os.chdir(ROOT)
MINE = ['ADV-0127','ADV-0128','ARC-0001','ARC-0012','ARC-0013','ARC-0015','ARC-0019','ARC-0020','ARC-0021','ARC-0047','ARC-0048','ARC-0054']
PROG = open(os.path.join(ROOT,'_p2-shard2-w4-review','battery_progress.jsonl'),'w',encoding='utf-8')
def log(o):
    PROG.write(json.dumps(o, default=str)+'\n'); PROG.flush()

def jl(p):
    with open(p, encoding='utf-8') as f: return json.load(f)
def sha_norm(path):
    with open(path,'rb') as f: b = f.read()
    return hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest(), len(b), b.count(b'\r\n')

sys.path.insert(0, os.path.join(ROOT,'platform','lib'))
import schema_resolver

cat = jl(os.path.join(ROOT,'command-center','WORK-UNIT-CATALOG.json'))
byid = {u['id']: u for u in cat['work_units'] if 'id' in u}
puman = jl(os.path.join(ROOT,'command-center','UNIT-ARTIFACT-MANIFEST.json'))
puman_rows = {r['unit_id']: r for r in puman.get('artifacts', [])}

results = {}
for uid in MINE:
    r = {'unit': uid}
    e = byid[uid]
    op, osch = e['output_path'], e['output_schema']
    r['output_path'] = op; r['output_schema'] = osch
    art = None
    if not os.path.exists(op):
        r['artifact'] = 'MISSING'
    else:
        raw = open(op,'rb').read()
        r['artifact_bytes_raw'] = len(raw)
        try:
            art = json.loads(raw.decode('utf-8')); r['artifact_parses'] = True
            if isinstance(art, dict):
                top_state = {k: art.get(k) for k in ('state','status') if k in art}
                r['top_level_state_status'] = top_state
                r['self_blocked'] = any(v in ('BLOCKED','FAILED') for v in top_state.values())
                r['artifact_top_keys'] = sorted(art.keys())[:25]
            else:
                r['self_blocked'] = False; r['top_level_state_status'] = 'non-dict:'+type(art).__name__
        except Exception as ex:
            r['artifact_parses'] = False; r['artifact_parse_error'] = str(ex)[:150]
    try:
        man = jl(os.path.join(ROOT,'command-center','p2-wave','probes',uid,'UNIT-ARTIFACT-MANIFEST.json'))
        rows = man.get('artifacts', [])
        prim = [x for x in rows if x.get('role')=='primary']
        r['manifest_primary_row'] = prim[0] if prim else None
        r['manifest_row_count'] = len(rows)
        if prim and os.path.exists(op):
            live_sha, live_n, ncrlf = sha_norm(op)
            r['live_sha_norm'] = live_sha; r['live_bytes_raw'] = live_n; r['live_crlf_count'] = ncrlf
            r['sha_match_manifest'] = (live_sha == prim[0]['sha256'])
            r['manifest_bytes'] = prim[0].get('bytes')
            r['sha_target'] = prim[0]['path']
            r['sha_target_is_output_path'] = (prim[0]['path'] == op)
        pu = puman_rows.get(uid)
        if pu and os.path.exists(op):
            live_sha2, _, _ = sha_norm(op)
            r['program_wide_manifest_row'] = {'sha256': pu['sha256'], 'bytes': pu.get('bytes'), 'matches_live': live_sha2==pu['sha256']}
        else:
            r['program_wide_manifest_row'] = 'ABSENT'
    except Exception as ex:
        r['manifest_error'] = str(ex)[:200]
    pre_sha = sha_norm(op)[0] if os.path.exists(op) else None
    probes = []
    try:
        sr = jl(os.path.join(ROOT,'command-center','p2-wave','probes',uid,'SUBAGENT-RETURN.json'))
        probes = sr.get('named_probes') or []
    except Exception as ex:
        r['subagent_return_error'] = str(ex)[:150]
    r['probes'] = []
    env = dict(os.environ); env['PYTHONDONTWRITEBYTECODE'] = '1'
    for p in probes:
        cmd = p.get('command','')
        args = cmd.split()
        if args and args[0] == 'python3': args[0] = 'python'
        t0 = time.time()
        try:
            cp = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, timeout=900)
            out = (cp.stdout or b'') + (cp.stderr or b'')
            out_s = out.decode('utf-8', errors='replace')
            sent = re.search('SUCCESS:'+re.escape(uid), out_s)
            r['probes'].append({'id': p.get('id'), 'cmd_tail': ' '.join(args[-3:]), 'exit': cp.returncode,
                                'dur_s': round(time.time()-t0,1), 'success_sentinel': bool(sent),
                                'out_tail': out_s[-300:]})
        except subprocess.TimeoutExpired:
            r['probes'].append({'id': p.get('id'), 'exit': 'TIMEOUT', 'dur_s': round(time.time()-t0,1)})
        except Exception as ex:
            r['probes'].append({'id': p.get('id'), 'exit': 'SPAWN-ERR', 'err': str(ex)[:150]})
    if pre_sha and os.path.exists(op):
        post_sha = sha_norm(op)[0]
        r['artifact_mutated_by_probes'] = (post_sha != pre_sha)
    if art is not None:
        try:
            errs = schema_resolver.validate_artifact(art, osch)
            r['schema_violations'] = len(errs)
            r['schema_errors_sample'] = errs[:5]
        except Exception as ex:
            r['schema_resolver_error'] = str(ex)[:200]
    results[uid] = r
    log(r)
    print('DONE', uid, flush=True)

json.dump(results, open(os.path.join(ROOT,'_p2-shard2-w4-review','battery_results.json'),'w',encoding='utf-8'), indent=1)
print('BATTERY COMPLETE')
