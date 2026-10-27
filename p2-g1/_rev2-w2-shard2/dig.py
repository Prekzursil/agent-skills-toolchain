import json
r = json.load(open(r'C:/Users/Prekzursil/p2-g1/_rev2-w2-shard2/battery_out.json', encoding='utf-8'))
for uid in ['ADV-0124','ADV-0127']:
    print('======', uid)
    for p in r[uid]['probe_reruns']:
        print(' rc=', p['exit_code'], 'secs=', p['seconds'], p['command'])
        print(' tail:', p['tail'][-700:].replace('\n', ' | ')[:900])
print()
print('====== ARC-0021 schema errors (3):')
for e in r['ARC-0021']['schema']['errors_first5']:
    print(' -', e)
print()
print('====== ADV-0124 schema errors first 8:')
for e in r['ADV-0124']['schema']['errors_first5']:
    print(' -', e)
