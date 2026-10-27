import json
import glob
import re
import collections
import os

REPO = r'C:/Users/Prekzursil/p2-g1'
by_shard = collections.defaultdict(set)
w3_re = re.compile(r'w3[\s_-]*shard\s*(\d+)|w3s(\d+)', re.I)
n_w3 = 0
for f in glob.glob(os.path.join(REPO, 'command-center/receipts/*.json')):
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception:
        continue
    rev = d.get('reviewer') or {}
    rid = str(rev.get('reviewer_id') or '')
    m = w3_re.search(rid)
    if m:
        n_w3 += 1
        shard = int(m.group(1) or m.group(2))
        uid = d.get('unit_id') or os.path.basename(f)[:-5]
        by_shard[shard].add((uid, rev.get('verdict'), d.get('state')))

print('receipts with w3 reviewer ids:', n_w3)
allids = set()
for shard in sorted(by_shard):
    ids = sorted(x[0] for x in by_shard[shard])
    allids.update(ids)
    print(f'w3 shard {shard}: {len(ids)} units: {ids}')
print('total units closed by w3 reviewers:', len(allids))
