"""Independent reviewer wave-4 shard-5: static phase (no probes).
Checks per unit: exists/non-empty/parses/obj, unit_id binding, sentinel binding,
state not self-blocked (no nested markers), DECLARED output_schema validation,
manifest primary row sha match (CRLF->LF), SUBAGENT-RETURN DELIVERED.
Writes _reviewer-w4s5/static_results.json ; prints one line per unit.
"""
import json, os, hashlib

os.chdir(os.path.expanduser('~/p2-g1'))
import jsonschema

MINE = ['AUD-0084','AUD-0096','BLD-0001','BLD-0002','BLD-0010','BLD-0016',
        'BLD-0023','BLD-0024','BLD-0027','BLD-0028','BLD-0037','BLD-0042']
BAD_STATES = {'BLOCKED','FAILED','SEVERED','TIMEOUT'}
BS = chr(92)

def sha_norm(path):
    raw = open(path,'rb').read()
    return (hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest(),
            ('CRLF' if b'\r\n' in raw else 'LF'), len(raw))

def schemas_for(field):
    parts = [p for p in str(field).split(' + ')]
    out = []
    for p in parts:
        p = p.strip().replace(BS,'/')
        token = p.split(' ')[0]
        out.append(token)
    return out

cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
byid = {u['id']: u for u in cat['work_units']}

results = {}
for uid in MINE:
    checks = {}
    entry = byid[uid]
    op = str(entry['output_path']).replace(BS,'/')
    checks['catalog_entry'] = True
    art = None

    # 1. exists / non-empty / parses
    if not os.path.exists(op):
        checks['artifact_exists'] = 'missing: %s' % op
    elif os.path.getsize(op) == 0:
        checks['artifact_nonempty'] = 'zero bytes'
    else:
        checks['artifact_exists'] = True
        checks['artifact_nonempty'] = True
        try:
            art = json.load(open(op, encoding='utf-8'))
            checks['artifact_parses'] = True
        except Exception as ex:
            checks['artifact_parses'] = '%s: %s' % (type(ex).__name__, str(ex)[:120])

    if isinstance(art, dict):
        checks['artifact_is_object'] = True
        checks['unit_id_binding'] = True if art.get('unit_id') == uid else 'unit_id=%r' % art.get('unit_id')
        sent = art.get('sentinel')
        checks['sentinel_binds'] = True if (isinstance(sent,str) and uid in sent) else 'sentinel=%r' % str(sent)[:60]
        checks['sentinel_matches_catalog'] = True if sent == entry.get('completion_sentinel') else 'sentinel != catalog completion_sentinel'
        st = art.get('state')
        checks['not_self_blocked'] = True if st not in BAD_STATES else 'state=%s' % st
        s = json.dumps(art)
        for marker in ('"state": "BLOCKED"', '"verdict": "BLOCKED"', '"status": "BLOCKED"'):
            if marker in s:
                checks['not_self_blocked'] = 'nested marker %s' % marker
        rv = art.get('reviewer') or {}
        checks['reviewer_verdict_pass'] = True if rv.get('verdict') == 'PASS' else 'reviewer.verdict=%r' % rv.get('verdict')
        checks['reviewer_independent'] = True if rv.get('independent') is True else 'reviewer.independent != true'
        checks['state_success'] = True if st == 'SUCCESS' else 'state=%s' % st
        # DECLARED schema validation
        for i, spath in enumerate(schemas_for(entry.get('output_schema'))):
            key = 'schema_%d_%s' % (i, os.path.basename(spath))
            try:
                schema = json.load(open(spath, encoding='utf-8'))
                jsonschema.validate(art, schema)
                checks[key] = True
            except jsonschema.ValidationError as ex:
                checks[key] = 'FAIL: %s' % str(ex.message)[:200]
            except Exception as ex:
                checks[key] = 'unreadable: %s' % str(ex)[:140]
    elif 'artifact_parses' in checks and checks['artifact_parses'] is True:
        checks['artifact_is_object'] = 'not a JSON object'

    # manifest sha match (primary row = path == output_path)
    try:
        man = json.load(open('command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json' % uid, encoding='utf-8'))
        rows = man.get('artifacts') if isinstance(man, dict) else man
        match = None
        if isinstance(rows, list):
            for a in rows:
                if isinstance(a, dict) and str(a.get('path','')).replace(BS,'/') == op:
                    match = a
        if match is None:
            checks['manifest_primary_row'] = 'no row with path==%s' % op
        else:
            live, eol, rawlen = sha_norm(op)
            checks['manifest_primary_row'] = True if (match.get('present') is True and match.get('sha256') == live) else 'manifest sha=%s.. live=%s.. present=%s eol=%s' % (str(match.get('sha256'))[:16], live[:16], match.get('present'), eol)
            checks['manifest_bytes'] = True if match.get('bytes') == rawlen else 'manifest bytes=%s raw=%s' % (match.get('bytes'), rawlen)
    except Exception as ex:
        checks['manifest_primary_row'] = '%s: %s' % (type(ex).__name__, str(ex)[:120])

    # SUBAGENT-RETURN
    try:
        ret = json.load(open('command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json' % uid, encoding='utf-8'))
        checks['subagent_return_delivered'] = True if ret.get('status') == 'DELIVERED' else 'status=%s' % ret.get('status')
    except Exception as ex:
        checks['subagent_return_delivered'] = '%s: %s' % (type(ex).__name__, str(ex)[:100])

    ok = all(v is True for v in checks.values())
    rec = {'ok': ok, 'checks': checks}
    if os.path.exists(op) and os.path.getsize(op) > 0:
        live, eol, rawlen = sha_norm(op)
        rec['sha_before_probes'] = live
        rec['eol'] = eol
    results[uid] = rec

    print('%s: %s' % (uid, 'ALL-HOLD' if ok else 'FAIL'))
    for k, v in checks.items():
        if v is not True:
            print('    %s: %s' % (k, v))

json.dump(results, open('_reviewer-w4s5/static_results.json','w'), indent=1)
bad = [u for u,v in results.items() if not v['ok']]
print()
print('STATIC PHASE:', 'ALL 12 ALL-HOLD' if not bad else 'FAILING: %s' % bad)
