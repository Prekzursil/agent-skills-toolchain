from wslrun import read_unc
import json
cat = json.loads(read_unc('/home/prekzursil/p2-g1/command-center/WORK-UNIT-CATALOG.json'))
units = {u['id']: u for u in cat.get('work_units', [])}
print('catalog units:', len(units))
mine = ['ADV-0005', 'AUD-0031', 'AUD-0043', 'AUD-0044', 'AUD-0055', 'AUD-0095', 'BLD-0010', 'BLD-0013', 'BLD-0014', 'BLD-0031', 'BLD-0032', 'BLD-0037', 'BLD-0044', 'BLD-0048', 'BLD-0057']
out = {}
for uid in mine:
    u = units.get(uid)
    if u is None:
        print(uid, 'CATALOG-MISSING')
        continue
    out[uid] = u
    print('====', uid)
    print(json.dumps(u, indent=1)[:2600])
with open('catalog_mine.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=1)
