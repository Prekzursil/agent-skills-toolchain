import json
import sys

import jsonschema

unit = sys.argv[1] if len(sys.argv) > 1 else 'ADV-0038'
art_path = f'command-center/adversarial/{unit}-{"revocation-propagation-to-caches" if unit == "ADV-0038" else ""}'
# resolve output_path from catalog instead
cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
unit_rec = next(u for u in cat['work_units'] if u['id'] == unit)
out = REPO = None
import os
from pathlib import Path
repo = Path(os.getcwd())
doc = json.loads((repo / unit_rec['output_path']).read_text(encoding='utf-8'))
schema = json.loads((repo / unit_rec['output_schema']).read_text(encoding='utf-8'))
errs = sorted(
    jsonschema.Draft202012Validator(schema).iter_errors(doc),
    key=lambda e: str(list(e.absolute_path)),
)
print(f'{unit} schema errors: {len(errs)}')
for e in errs[:40]:
    print(' *', list(e.absolute_path), '->', str(e.message)[:220])
