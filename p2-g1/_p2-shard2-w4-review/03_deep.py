import json, os, glob
os.chdir(os.path.expanduser('~/p2-g1'))
def jl(p):
    with open(p, encoding='utf-8') as f: return json.load(f)
cat = jl('command-center/WORK-UNIT-CATALOG.json')
byid = {u['id']: u for u in cat['work_units'] if 'id' in u}
for uid in ('ADV-0127','ARC-0001'):
    print('='*20, uid, 'FULL CATALOG ENTRY')
    print(json.dumps(byid[uid], indent=1)[:4000])
print('='*20, 'MANIFEST rows ADV-0127/0128')
man = jl('command-center/UNIT-ARTIFACT-MANIFEST.json')
for r in man['artifacts']:
    if r['unit_id'] in ('ADV-0127','ADV-0128'):
        print(json.dumps(r, indent=1))
print('='*20, 'manifest contract keys')
print(json.dumps(man.get('contract'), indent=1)[:1500])
print('='*20, 'receipt ADV-0127 full')
print(json.dumps(jl('command-center/receipts/ADV-0127.json'), indent=1)[:3500])
print('='*20, 'receipt ARC-0001 full')
print(json.dumps(jl('command-center/receipts/ARC-0001.json'), indent=1)[:3500])
print('='*20, 'other manifest files anywhere')
hits = glob.glob('**/UNIT-ARTIFACT-MANIFEST*', recursive=True) + glob.glob('**/*ARTIFACT-MANIFEST*', recursive=True)
print(sorted(set(hits))[:20])
