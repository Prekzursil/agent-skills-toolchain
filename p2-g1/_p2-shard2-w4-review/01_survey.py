import json, os, sys
os.chdir(os.path.expanduser('~/p2-g1'))
MINE = ['ADV-0127','ADV-0128','ARC-0001','ARC-0012','ARC-0013','ARC-0015','ARC-0019','ARC-0020','ARC-0021','ARC-0047','ARC-0048','ARC-0054']

def jl(p):
    with open(p, encoding='utf-8') as f: return json.load(f)

cat = jl('command-center/WORK-UNIT-CATALOG.json')
units = cat['units'] if isinstance(cat, dict) and 'units' in cat else cat
if isinstance(units, list): units = {u['id']: u for u in units}

man = jl('command-center/UNIT-ARTIFACT-MANIFEST.json')
manrows = {r['unit_id']: r for r in man.get('artifacts', [])}

out = {}
for uid in MINE:
    e = units.get(uid)
    rec = {'in_catalog': e is not None}
    if e:
        rec['output_path'] = e.get('output_path')
        rec['output_schema'] = e.get('output_schema')
        rec['probes'] = e.get('probes')
        rec['deps'] = e.get('dependencies')
        rec['owner_gate'] = e.get('owner_approval_required')
        op = e.get('output_path')
        if op and os.path.exists(op):
            sz = os.path.getsize(op)
            rec['artifact_size'] = sz
            if sz > 0:
                try:
                    art = jl(op)
                    rec['artifact_parses'] = True
                    s = json.dumps(art)
                    rec['self_blocked'] = bool('"state": "BLOCKED"' in s or '"state":"BLOCKED"' in s or '"status": "BLOCKED"' in s or '"verdict": "BLOCKED"' in s)
                    rec['artifact_keys'] = list(art.keys())[:15] if isinstance(art, dict) else type(art).__name__
                except Exception as ex:
                    rec['artifact_parses'] = False
                    rec['parse_error'] = str(ex)[:200]
        else:
            rec['artifact_size'] = 'MISSING'
    r = manrows.get(uid)
    rec['manifest_row'] = r
    # receipt
    rp = f'command-center/receipts/{uid}.json'
    if os.path.exists(rp):
        try:
            recp = jl(rp)
            rec['receipt'] = {k: recp.get(k) for k in ('unit_id','state','reviewer','notes')}
            rec['receipt_path'] = rp
        except Exception as ex:
            rec['receipt'] = f'unparseable: {ex}'
    else:
        rec['receipt'] = 'NO RECEIPT FILE'
    out[uid] = rec

json.dump(out, open('_p2-shard2-w4-review/survey.json','w'), indent=1)
for uid in MINE:
    r = out[uid]
    print('='*8, uid)
    print(' catalog:', r['in_catalog'], '| artifact size:', r.get('artifact_size'), '| parses:', r.get('artifact_parses'), '| self_blocked:', r.get('self_blocked'))
    print(' op:', r.get('output_path'))
    print(' schema:', r.get('output_schema'))
    print(' probes:', json.dumps(r.get('probes'))[:200])
    print(' manifest:', 'row' if r.get('manifest_row') else 'NONE', json.dumps(r.get('manifest_row'))[:200])
    print(' receipt:', json.dumps(r.get('receipt'))[:300])
