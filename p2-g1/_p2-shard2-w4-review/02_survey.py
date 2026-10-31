import json, os
os.chdir(os.path.expanduser('~/p2-g1'))
MINE = ['ADV-0127','ADV-0128','ARC-0001','ARC-0012','ARC-0013','ARC-0015','ARC-0019','ARC-0020','ARC-0021','ARC-0047','ARC-0048','ARC-0054']
def jl(p):
    with open(p, encoding='utf-8') as f: return json.load(f)
cat = jl('command-center/WORK-UNIT-CATALOG.json')
byid = {}
for u in cat['work_units']:
    byid.setdefault(u.get('id'), []).append(u)
man = jl('command-center/UNIT-ARTIFACT-MANIFEST.json')
manrows = {r['unit_id']: r for r in man.get('artifacts', [])}
out = {}
for uid in MINE:
    es = byid.get(uid, [])
    rec = {'catalog_count': len(es)}
    if es:
        e = es[0]
        rec['entry'] = {k: e.get(k) for k in ('output_path','output_schema','probes','dependencies','owner_approval_required','reviewer_requirement')}
        op = e.get('output_path')
        if op and os.path.exists(op):
            sz = os.path.getsize(op); rec['artifact_size'] = sz
            if sz:
                try:
                    art = jl(op); rec['artifact_parses'] = True
                    s = json.dumps(art)
                    rec['self_blocked'] = ('"state": "BLOCKED"' in s) or ('"state":"BLOCKED"' in s) or ('"status": "BLOCKED"' in s) or ('"status":"BLOCKED"' in s)
                    rec['artifact_keys'] = list(art.keys())[:20] if isinstance(art, dict) else type(art).__name__
                except Exception as ex:
                    rec['artifact_parses'] = False; rec['parse_error'] = str(ex)[:200]
        else:
            rec['artifact_size'] = 'MISSING'
    rec['manifest_row'] = manrows.get(uid)
    rp = f'command-center/receipts/{uid}.json'
    rec['receipt_path'] = rp if os.path.exists(rp) else None
    if rec['receipt_path']:
        recp = jl(rp)
        rec['receipt_state'] = recp.get('state')
        rev = recp.get('reviewer') or {}
        rec['receipt_reviewer'] = {k: rev.get(k) for k in ('reviewer_id','verdict','independent','reviewed_at','notes')}
    out[uid] = rec
json.dump(out, open('_p2-shard2-w4-review/survey2.json','w',encoding='utf-8'), indent=1)
for uid in MINE:
    r = out[uid]
    print('='*10, uid, '| catalog entries:', r['catalog_count'])
    if r['catalog_count']:
        e = r['entry']
        print('  op:', e['output_path'])
        print('  schema:', e['output_schema'])
        print('  probes:', json.dumps(e['probes'])[:400])
        print('  deps:', e['dependencies'], '| owner_gate:', e['owner_approval_required'])
        print('  size:', r.get('artifact_size'), '| parses:', r.get('artifact_parses'), '| self_blocked:', r.get('self_blocked'))
    print('  manifest:', json.dumps(r['manifest_row'])[:250] if r['manifest_row'] else 'NONE')
    print('  receipt:', r['receipt_state'], '|', json.dumps(r['receipt_reviewer'])[:250])
