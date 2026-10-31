import json, sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
root = Path(r'C:/Users/Prekzursil/p2-g1')
MY12 = ['ADV-0005','ADV-0010','ADV-0014','ADV-0015','ADV-0018','ADV-0019',
        'ADV-0022','ADV-0023','ADV-0024','ADV-0028','ADV-0029','ADV-0037']
catall = json.loads((root/'command-center/WORK-UNIT-CATALOG.json').read_text(encoding='utf-8'))
byid = {u.get('id'): u for u in catall['work_units']}
print('contract:', json.dumps(catall.get('contract'))[:400])
print('defaults:', json.dumps(catall.get('defaults'))[:400])
print()
for uid in MY12:
    u = byid.get(uid)
    if not u:
        print(uid, 'NO CATALOG ENTRY'); continue
    print('='*80)
    print(uid, '|', u.get('title'))
    print(' output_path:', u.get('output_path'))
    print(' output_schema:', u.get('output_schema'))
    print(' probes:', json.dumps(u.get('probes'), indent=1))
    print(' dependencies:', u.get('dependencies'))
    print(' reviewer_requirement:', u.get('reviewer_requirement'))
    print(' owner_approval_required:', u.get('owner_approval_required'))
    print(' evidence_requirement:', str(u.get('evidence_requirement'))[:300])
    print(' completion_sentinel:', str(u.get('completion_sentinel'))[:300])
