import json, os, glob, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
root = r'C:/Users/Prekzursil/p2-g1'
probes = root + '/command-center/p2-wave/probes'
receipts = root + '/command-center/receipts'

pending = []
for f in sorted(glob.glob(receipts + '/*.json')):
    uid = os.path.basename(f)[:-5]
    if uid == 'REL-0011.cdx':
        print('NOTE: weird receipt', uid); continue
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception:
        continue
    st = d.get('state')
    if st == 'SUCCESS':
        continue
    man = os.path.join(probes, uid, 'UNIT-ARTIFACT-MANIFEST.json')
    has_man = os.path.isfile(man)
    fc = (d.get('failure') or {}).get('classification')
    pending.append((uid, st, has_man, fc))

print('pending total:', len(pending))
with_man = [p for p in pending if p[2]]
without = [p for p in pending if not p[2]]
print('with manifest:', len(with_man), ' without:', len(without))
print()
print('PENDING WITH MANIFEST (sorted):')
for p in with_man:
    print(' ', p[0], p[1], p[3])
print()
print('PENDING WITHOUT MANIFEST:')
for p in without:
    print(' ', p[0], p[1], p[3])
