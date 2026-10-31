from wslrun import read_unc, wsl_bash
import json, hashlib

# 1. Parse READY units
raw = read_unc('/home/prekzursil/p2-g1/command-center/READY-UNITS.json')
doc = json.loads(raw)
ready = doc.get('ready_units') or doc.get('ready') or doc.get('units')
print('ready count:', len(ready))

# 2. Filter: id hash-modulo 6 === 3, in python (hashlib on each id)
mine = []
for uid in ready:
    h = hashlib.sha256(uid.encode('utf-8')).hexdigest()
    if int(h, 16) % 6 == 3:
        mine.append(uid)
print('total matching mod6==3:', len(mine))
print('first 15:', mine[:15])
with open('my_units.json', 'w') as f:
    json.dump({'ready_total': len(ready), 'mod3_total': len(mine), 'first15': mine[:15]}, f, indent=1)
