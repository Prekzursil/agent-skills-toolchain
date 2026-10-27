"""Run the program's OWN authoritative predicate on the w4s5 12 units.
Instrument: command-center/ready_units.py::artifact_delivered (the DELIVERED
predicate unitgate uses) + platform/lib/receipt_schema_gate.py::evaluate_gate_a
(the 12-condition completion predicate). No hand-rolled schema logic.
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

ru = load_mod('ready_units', os.path.join(REPO, 'command-center/ready_units.py'))
ru.REPO = REPO
rsg = load_mod('rsg', os.path.join(REPO, 'platform/lib/receipt_schema_gate.py'))

resolver = ru._load_resolver()
print('resolver loaded:', resolver is not None)

cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
byid = {u['id']: u for u in cat['work_units']}
MINE = ['AUD-0084','AUD-0096','BLD-0001','BLD-0002','BLD-0010','BLD-0016',
        'BLD-0023','BLD-0024','BLD-0027','BLD-0028','BLD-0037','BLD-0042']

out = {}
for uid in MINE:
    unit = byid[uid]
    ok, why = ru.artifact_delivered(unit, resolver)
    # 12-condition predicate on the receipt doc
    doc = json.load(open(unit['output_path'].replace(chr(92), '/'), encoding='utf-8'))
    gate = rsg.evaluate_gate_a(doc, repo_root=REPO, verify_filesystem=True)
    blocking = [(c.n, c.outcome, c.basis[:160]) for c in gate.conditions if c.blocking]
    out[uid] = {'artifact_delivered': [ok, why],
                'gate_state': gate.state,
                'schema_errors': gate.schema_errors[:3],
                'blocking_conditions': blocking}
    print('== %s: artifact_delivered=%s(%s) | gate all-satisfied=%s' % (
        uid, ok, why, not blocking))
    if gate.schema_errors:
        print('   schema_errors:', gate.schema_errors[:2])
    for n, oc, basis in blocking:
        print('   cond-%d %s: %s' % (n, oc, basis))

json.dump(out, open('_reviewer-w4s5/program_predicate_results.json', 'w'), indent=1)
clean = [u for u, v in out.items() if v['artifact_delivered'][0] and not v['blocking_conditions'] and not v['schema_errors']]
print()
print('PROGRAM PREDICATE: %d/12 clean: %s' % (len(clean), clean))
