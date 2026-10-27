"""Capture full C2 schema-error lists for the w4s5 verdict record (precedent: w4s8/schema_errors_full.json).
Instrument: platform/lib/receipt_schema_gate.py::validate_receipt (the program's own).
Also records per-unit first-failing-check classification used in verdicts.
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

rsg = load_mod('rsg2', REPO / 'platform/lib/receipt_schema_gate.py')

MINE = ['AUD-0084','AUD-0096','BLD-0001','BLD-0002','BLD-0010','BLD-0016',
        'BLD-0023','BLD-0024','BLD-0027','BLD-0028','BLD-0037','BLD-0042']
cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
byid = {u['id']: u for u in cat['work_units']}

out = {}
for uid in MINE:
    doc = json.load(open(byid[uid]['output_path'].replace(chr(92), '/'), encoding='utf-8'))
    errs = rsg.validate_receipt(doc)
    out[uid] = errs
    print(uid, len(errs), 'error(s)')

json.dump(out, open('_reviewer-w4s5/schema_errors_full.json', 'w'), indent=1)
print('wrote _reviewer-w4s5/schema_errors_full.json')
