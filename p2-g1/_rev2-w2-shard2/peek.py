import json, os
base = r'C:\Users\Prekzursil\p2-g1'
u = 'ADV-0124'
d = json.load(open(os.path.join(base, 'command-center', 'receipts', u + '.json'), encoding='utf-8'))
print('KEYS:', sorted(d.keys()))
print(json.dumps(d, indent=1)[:3000])
