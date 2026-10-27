import json, os
os.chdir(os.path.expanduser('~/p2-g1'))
BS = chr(92)
mine = ['IMP-0002','IMP-0006','IMP-0022','IMP-0031','IMP-0035','IMP-0036','IMP-0037','IMP-0038','IMP-0041','IMP-0044','IMP-0051','IMP-0068']
cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
byid = {u['id']: u for u in cat['work_units']}
out = {}
for uid in mine:
    e = byid.get(uid)
    rec = {}
    if not e:
        print(uid, 'NOT IN CATALOG'); out[uid] = rec; continue
    op = str(e.get('output_path','')).replace(BS, '/')
    sch = str(e.get('output_schema','')).replace(BS, '/')
    rec['output_path'] = op
    rec['output_schema'] = sch
    rec['owner_gate'] = e.get('owner_approval_required')
    rec['deps'] = e.get('dependencies')
    art_exists = os.path.exists(op)
    art_size = os.path.getsize(op) if art_exists else None
    rec['artifact_exists'] = art_exists
    rec['artifact_size'] = art_size
    print('==', uid, '| gate:', rec['owner_gate'], '| artifact:', art_exists, art_size)
    print('   out:', op)
    print('   schema:', sch)
    pdir = f'command-center/p2-wave/probes/{uid}'
    if os.path.isdir(pdir):
        files = sorted(os.listdir(pdir))
        rec['probe_files'] = files
        print('   probe dir:', files)
    else:
        rec['probe_files'] = None
        print('   probe dir: MISSING')
    rp = f'command-center/receipts/{uid}.json'
    if os.path.exists(rp):
        r = json.load(open(rp, encoding='utf-8'))
        rec['receipt_state'] = r.get('state')
        rec['reviewer'] = r.get('reviewer')
        print('   receipt state:', r.get('state'), '| reviewer:', json.dumps(r.get('reviewer'))[:150])
    else:
        rec['receipt'] = 'MISSING'
        print('   receipt: MISSING')
    out[uid] = rec
json.dump(out, open('_reviewer-w4s8/survey.json','w'), indent=1)
