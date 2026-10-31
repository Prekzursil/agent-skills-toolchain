import sys, json, os
sys.path.insert(0, r'C:/Users/Prekzursil/p2-g1/platform/lib')
import receipt_schema_gate as g
base = 'C:/Users/Prekzursil/p2-g1/command-center/receipts'
for u in ['ARC-0001','ARC-0013','ADV-0124','ARC-0012']:
    doc = json.load(open(os.path.join(base, u + '.json'), encoding='utf-8'))
    errs = g.validate_receipt(doc)
    print(u, doc.get('state'), len(errs), 'errors:')
    for e in errs: print('   -', str(e)[:200])
