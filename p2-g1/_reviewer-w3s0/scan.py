import json, os, re, glob

root = r'C:/Users/Prekzursil/p2-g1'

# 1. Look at the w3-entries files
for f in glob.glob(root + '/_p2-shard*-w3-entries.json'):
    print('---', os.path.basename(f))
    d = json.load(open(f, encoding='utf-8'))
    if isinstance(d, list):
        print('list of', len(d), 'first:', json.dumps(d[0], indent=1)[:300] if d else '')
    else:
        print('dict keys:', list(d)[:10])

# 2. Look for any file mentioning shard 0 wave 3
for pat in ['*shard0*w3*', '*w3*shard0*', '*wave3*shard*']:
    for f in glob.glob(root + '/' + pat):
        print('MATCH:', f)
