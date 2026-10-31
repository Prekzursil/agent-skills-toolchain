import json, os
base = r'C:\Users\Prekzursil\p2-g1'
d = json.load(open(os.path.join(base,'command-center','receipts','ARC-0001.json'), encoding='utf-8'))
print('REVIEWER FULL:')
print(json.dumps(d['reviewer'], indent=1))
print('STATE:', d.get('state'), '| SENTINEL:', d.get('sentinel'))
print('EXTENSIONS:', json.dumps(d.get('extensions'), indent=1)[:800] if d.get('extensions') else None)
print('GATE_NOTE:', d.get('gate_note'))
