import json, os, sys, importlib.util
os.chdir(os.path.expanduser('~/p2-g1'))
spec = importlib.util.spec_from_file_location('rsg', 'platform/lib/receipt_schema_gate.py')
mod = importlib.util.module_from_spec(spec)
sys.modules['rsg'] = mod
spec.loader.exec_module(mod)
mine = ['IMP-0002','IMP-0006','IMP-0022','IMP-0031','IMP-0035','IMP-0036','IMP-0037','IMP-0038','IMP-0041','IMP-0044','IMP-0051','IMP-0068']
out = {}
for uid in mine:
    doc = json.load(open(f'command-center/receipts/{uid}.json', encoding='utf-8'))
    errs = mod.validate_receipt(doc)
    out[uid] = errs
    print(f"== {uid}: {len(errs)} schema errors")
    for e in errs:
        print('   -', e[:150])
json.dump(out, open('_reviewer-w4s8/schema_errors_full.json','w'), indent=1)
