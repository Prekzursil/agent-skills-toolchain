import json, os
base = r'C:\Users\Prekzursil\p2-g1'
d = json.load(open(os.path.join(base,'command-center','receipts','ARC-0001.json'), encoding='utf-8'))
print(json.dumps(d, indent=1)[:3500])
print()
sr = json.load(open(os.path.join(base,'command-center','p2-wave','probes','ARC-0001','SUBAGENT-RETURN.json'), encoding='utf-8'))
print('SUBAGENT-RETURN KEYS:', sorted(sr.keys()))
print(json.dumps(sr, indent=1)[:2000])
