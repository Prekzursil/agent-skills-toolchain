import importlib.util, json, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('gate', 'platform/lib/receipt_schema_gate.py')
mod = importlib.util.module_from_spec(spec)
sys.modules['gate'] = mod
spec.loader.exec_module(mod)
mine = ['TST-0283','TST-0284','TST-0288','TST-0297','TST-0303','TST-0309','TST-0313','TST-0315','TST-0319','TST-0322','TST-0328','TST-0330']
schema = mod.load_schema()
v = mod.build_validator(schema)
import jsonschema
for uid in mine:
    doc = json.loads(Path('command-center/receipts/%s.json' % uid).read_text(encoding='utf-8'))
    errs = sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path))
    print('=== %s (%d errors)' % (uid, len(errs)))
    for e in errs:
        path = '/'.join(str(x) for x in e.absolute_path) or '<root>'
        print('   %s: %s' % (path, e.message[:140]))
