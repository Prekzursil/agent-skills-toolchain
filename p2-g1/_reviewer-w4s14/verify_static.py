import json, hashlib, sys, os
os.chdir(os.path.expanduser('~/p2-g1'))

IDS = ['REL-0017','REL-0020','REL-0021','REL-0022','RES-0004','RES-0009','RES-0011','RES-0037','RES-0044','RES-0049','RES-0077','RES-0079']
cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
units = {u['id']: u for u in cat['work_units']}

def norm_sha(p):
    b = open(p,'rb').read()
    return hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest()

results = {}
for i in IDS:
    r = {'id': i}
    u = units[i]
    op = u['output_path']
    r['output_path'] = op
    # 1. exists / non-empty / parses
    if not os.path.isfile(op):
        r['artifact'] = 'MISSING'
        results[i] = r; continue
    size = os.path.getsize(op)
    r['bytes'] = size
    if size == 0:
        r['artifact'] = 'EMPTY'
        results[i] = r; continue
    try:
        d = json.load(open(op, encoding='utf-8'))
        r['artifact'] = 'PARSE-OK'
    except Exception as e:
        r['artifact'] = 'PARSE-FAIL: %s' % e
        results[i] = r; continue
    # 2. manifest row
    mp = 'command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json' % i
    if not os.path.isfile(mp):
        r['manifest'] = 'MISSING'
        results[i] = r; continue
    m = json.load(open(mp, encoding='utf-8'))
    rows = [a for a in m.get('artifacts', []) if a.get('unit_id') == i or a.get('path','').endswith('/%s.json' % i) or os.path.basename(a.get('path','')) == os.path.basename(op)]
    r['manifest_rows'] = len(rows)
    live = norm_sha(op)
    r['live_sha'] = live
    r['sha_match'] = any(a.get('sha256') == live for a in rows)
    r['bytes_match'] = any(a.get('bytes') == size for a in rows)
    # 3. schema
    sp = u.get('output_schema')
    r['schema_path'] = sp
    if sp and os.path.isfile(sp):
        r['schema_present'] = True
    else:
        r['schema_present'] = False if sp else 'no-schema-declared'
    results[i] = r

print(json.dumps(results, indent=1))
