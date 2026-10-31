import json, os, glob, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
root = r'C:/Users/Prekzursil/p2-g1'
allids = {}
# entries files with w3
pats = [root + '/_p2-shard*-w3-entries.json', root + '/_shard*-w3-entries.json',
        root + '/_shard*-w3-my-entries.json']
for pat in pats:
    for f in glob.glob(pat):
        try:
            d = json.load(open(f, encoding='utf-8'))
        except Exception as e:
            print('SKIP', os.path.basename(f), e); continue
        if isinstance(d, list):
            ids = [u.get('id') for u in d if isinstance(u, dict)]
        elif isinstance(d, dict):
            ids = list(d.keys())
        else:
            ids = []
        name = os.path.basename(f)
        print(f"{name}: {len(ids)} -> {ids}")
        for i in ids:
            allids.setdefault(i, name)
print()
print('TOTAL distinct w3 unit ids from entries files:', len(allids))

# also check builder scratch dirs for wave 3 (dirs *_w3* or *_shardN-w3*)
