"""Green ladder across all 2,007 units (fresh, 2026-10-26):
L1 closure shape (state=SUCCESS + reviewer PASS + independent)
L2 L1 + admission-valid (receipt_validate C1-C4)
L3 L2 + 12-condition predicate clean (evaluate_gate_a, verify_filesystem=True)
Plus the not-green list grouped by reason.
"""
import importlib.util, json, os, sys
from pathlib import Path

os.chdir(os.path.expanduser('~/p2-g1'))
REPO = Path(os.getcwd())

def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

rsg = load_mod('rsg3', REPO / 'platform/lib/receipt_schema_gate.py')

cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
units = cat['work_units']

l1 = l2 = l3 = 0
not_green = []
for u in units:
    uid = u['id']
    op = str(u['output_path']).replace(chr(92), '/')
    try:
        doc = json.load(open(op, encoding='utf-8'))
    except Exception as ex:
        not_green.append((uid, 'unparseable', type(ex).__name__))
        continue
    rv = doc.get('reviewer') if isinstance(doc.get('reviewer'), dict) else {}
    st = doc.get('state')
    if not (st == 'SUCCESS' and rv.get('verdict') == 'PASS' and rv.get('independent') is True):
        not_green.append((uid, 'not-closed', 'state=%s reviewer=%s' % (st, rv.get('verdict'))))
        continue
    l1 += 1
    errs = rsg.validate_receipt(doc)
    if errs:
        not_green.append((uid, 'closed-but-schema-invalid', '%d errors; first: %s' % (len(errs), errs[0][:100])))
        continue
    l2 += 1
    gate = rsg.evaluate_gate_a(doc, repo_root=REPO, verify_filesystem=True)
    blocking = [c for c in gate.conditions if c.blocking]
    if blocking:
        not_green.append((uid, 'closed-valid-but-predicate-blocked',
                          '; '.join('cond-%d %s' % (c.n, c.basis[:70]) for c in blocking[:3])))
        continue
    l3 += 1

out = {'units': len(units), 'L1_closure_shape': l1, 'L2_plus_admission_valid': l2,
       'L3_plus_predicate_clean': l3, 'not_green': not_green}
json.dump(out, open('_reviewer-w4s5/green_ladder.json', 'w'), indent=1)
print('units:', len(units))
print('L1 closure shape (SUCCESS + PASS + independent):', l1)
print('L2 = L1 + admission-valid (C1-C4):            ', l2)
print('L3 = L2 + 12-condition predicate clean:        ', l3)
from collections import Counter
print('not green reasons:', Counter(r for _, r, _ in not_green))
print('wrote _reviewer-w4s5/green_ladder.json')
