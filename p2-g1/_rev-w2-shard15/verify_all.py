import json, hashlib, subprocess, sys, os
from pathlib import Path
REPO = Path('C:/Users/Prekzursil/p2-g1')
MINE = ['IMP-0423','IMP-0430','IMP-0435','IMP-0437','IMP-0439','IMP-0442',
        'IMP-0448','IMP-0450','IMP-0460','IMP-0466','IMP-0467','IMP-0468']
NOT_DELIVERING = set(['BLOCKED','FAILED','SEVERED','TIMEOUT'])
HAVE_JS = True
try:
    import jsonschema
except Exception:
    HAVE_JS = False
NL = chr(10)
cat = json.loads((REPO/'command-center'/'WORK-UNIT-CATALOG.json').read_text(encoding='utf-8'))
wu = dict((u['id'], u) for u in cat['work_units'])
norm = lambda s: str(s).replace(chr(92), '/')
sha_norm = lambda p: hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
ENV = dict(os.environ)
ENV['PYTHONDONTWRITEBYTECODE'] = '1'
ENV['PYTHONIOENCODING'] = 'utf-8'
results = {}
for uid in MINE:
    u = wu[uid]
    out_rel = norm(u['output_path'])
    rp = REPO / out_rel
    r = {'artifact_path': out_rel}
    r['exists'] = rp.is_file()
    if rp.is_file():
        raw = rp.read_bytes()
        r['bytes'] = len(raw)
        try:
            doc = json.loads(raw.decode('utf-8'))
            r['parses'] = True
            st = str(doc.get('state') or '').upper()
            r['state'] = st
            r['self_blocked'] = st in NOT_DELIVERING
            r['unit_id_field'] = doc.get('unit_id') or doc.get('id')
            txt = raw.decode('utf-8', 'replace')
            sent = str(u.get('completion_sentinel') or '')
            r['sentinel_in_text'] = (sent in txt) if sent else None
            rv = doc.get('reviewer') or {}
            r['reviewer_verdict'] = rv.get('verdict')
            r['reviewer_independent'] = rv.get('independent')
            r['reviewer_id'] = rv.get('reviewer_id')
        except Exception as e:
            r['parses'] = False
            r['parse_err'] = repr(e)[:200]
    else:
        r['bytes'] = 0
    man_p = REPO/'command-center'/'p2-wave'/'probes'/uid/'UNIT-ARTIFACT-MANIFEST.json'
    r['manifest_exists'] = man_p.is_file()
    if man_p.is_file() and rp.is_file():
        try:
            m = json.loads(man_p.read_text(encoding='utf-8'))
            rows = [a for a in (m.get('artifacts') or [])
                    if norm(a.get('path','')) == out_rel or a.get('unit_id') == uid]
            live = sha_norm(rp)
            r['live_sha'] = live
            r['manifest_sha'] = rows[0].get('sha256') if rows else None
            r['sha_match'] = bool(rows) and rows[0].get('sha256') == live
            r['bytes_match'] = bool(rows) and rows[0].get('bytes') == rp.stat().st_size
        except Exception as e:
            r['manifest_parse_err'] = repr(e)[:200]
    sch_rel = norm(u.get('output_schema') or '')
    sch_p = REPO / sch_rel
    if rp.is_file() and sch_p.is_file() and r.get('parses'):
        try:
            schema = json.loads(sch_p.read_text(encoding='utf-8'))
            inst = json.loads(rp.read_text(encoding='utf-8'))
            if HAVE_JS:
                jsonschema.validate(inst, schema)
                r['schema'] = 'jsonschema:OK'
            else:
                req = schema.get('required') or []
                missing = [k for k in req if k not in inst]
                r['schema'] = 'structural:OK' if not missing else 'structural:MISSING=' + ','.join(missing)
        except Exception as e:
            r['schema'] = 'FAIL:' + str(e).replace(NL, ' ')[:250]
    else:
        r['schema'] = 'schema-file-missing:' + sch_rel
    results[uid] = r
for uid in sorted(results):
    r = results[uid]
    pdir = REPO/'command-center'/'p2-wave'/'probes'/uid
    probes = sorted(pdir.glob('probe*.py')) if pdir.is_dir() else []
    r['probe_runs'] = []
    for pb in probes:
        rel = pb.relative_to(REPO)
        try:
            cp = subprocess.run([sys.executable, '-B', str(rel)], cwd=str(REPO),
                                env=ENV, capture_output=True, text=True,
                                errors='replace', timeout=300)
            tail = (cp.stdout or cp.stderr or '')[-170:].replace(NL, ' | ')
            r['probe_runs'].append({'probe': pb.name, 'exit': cp.returncode, 'tail': tail})
        except Exception as e:
            r['probe_runs'].append({'probe': pb.name, 'exit': 'EXC', 'tail': repr(e)[:160]})
for uid in sorted(results):
    r = results[uid]
    basic = r.get('exists') and r.get('parses') and (not r.get('self_blocked')) and r.get('sentinel_in_text')
    sha_ok = r.get('sha_match')
    pk = r.get('probe_runs') or []
    probes_ok = (len(pk) >= 2) and all(p['exit'] == 0 for p in pk)
    print('== ' + uid + ': exists=%s parses=%s state=%s uid_field=%s sentinel=%s' % (
        r.get('exists'), r.get('parses'), r.get('state'), r.get('unit_id_field'), r.get('sentinel_in_text')))
    print('   reviewer: verdict=%s independent=%s id=%s' % (
        r.get('reviewer_verdict'), r.get('reviewer_independent'), r.get('reviewer_id')))
    print('   sha_match=%s bytes_match=%s schema=%s' % (sha_ok, r.get('bytes_match'), r.get('schema')))
    for p in pk:
        print('   probe ' + p['probe'] + ': exit=%s tail=%s' % (p['exit'], p['tail'][:110]))
    print('   GATE basic=%s sha=%s probes_ok=%s' % (bool(basic), sha_ok, probes_ok))
json.dump(results, open(str(REPO/'_rev-w2-shard15'/'results.json'), 'w', encoding='utf-8'), indent=1)
print('WROTE results.json jsonschema=' + str(HAVE_JS))
