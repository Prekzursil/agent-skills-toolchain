import json
import pathlib
import re

import jsonschema

REPO = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate')
contract = (REPO / 'command-center/p2-wave/probes/AUD-0095/contract.py').read_text(encoding='utf-8')
out_rel = re.search(r'OUT_REL\s*=\s*[\'"]([^\'"]+)[\'"]', contract).group(1)
schema_rel = re.search(r'SCHEMA_REL\s*=\s*[\'"]([^\'"]+)[\'"]', contract).group(1)
print('OUT_REL:', out_rel)
print('SCHEMA_REL:', schema_rel)
schema = json.loads((REPO / schema_rel).read_text(encoding='utf-8'))
doc = json.loads((REPO / out_rel).read_text(encoding='utf-8'))
v = jsonschema.Draft7Validator(schema)
for e in list(v.iter_errors(doc))[:10]:
    print('ERROR at', list(e.absolute_path), ':', e.message[:200])
