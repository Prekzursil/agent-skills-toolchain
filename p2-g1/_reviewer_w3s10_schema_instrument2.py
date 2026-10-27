import importlib.util
import json
import os
import sys
import warnings

REPO = r'C:/Users/Prekzursil/p2-g1'
os.environ.setdefault('AST_INTEGRATE_ROOT', REPO)
warnings.filterwarnings('ignore')

spec = importlib.util.spec_from_file_location('rw_units', os.path.join(REPO, '_reviewer_w3s10_units.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
UNITS = m.UNITS

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

# Instrument 2: raw draft-2020-12 validation against the physical schema
# that the DECLARED shim (command-center/schema/receipt.schema.json) delegates to.
with open(os.path.join(REPO, 'command-center', 'schema', 'receipt.schema.json'), encoding='utf-8') as f:
    shim = json.load(f)
print('shim $ref:', shim.get('$ref'))
print('shim $id :', shim.get('$id'))

with open(os.path.join(REPO, 'platform', 'schema', 'receipt.schema.json'), encoding='utf-8') as f:
    phys = json.load(f)
print('physical required:', phys.get('required'))
print('physical $defs:', sorted((phys.get('$defs') or {}).keys())[:10])

# Build a registry: shim URI -> shim doc, physical URI -> physical doc, per each $id.
def resource_of(doc):
    return Resource.from_contents(doc, default_specification=DRAFT202012)

registry = Registry()
for doc in (shim, phys):
    sid = doc.get('$id')
    if sid:
        registry = registry.with_resource(sid, resource_of(doc))

validator = Draft202012Validator(shim, registry=registry)

print()
print('=== Instrument 2: raw draft-2020-12 via shim $ref ===')
for uid in UNITS:
    art = os.path.join(REPO, 'command-center', 'receipts', uid + '.json')
    inst = json.load(open(art, encoding='utf-8'))
    errs = sorted(validator.iter_errors(inst), key=lambda e: str(e.absolute_path))
    print('%s instrument2_errors=%d' % (uid, len(errs)))
    for e in errs[:3]:
        print('   ', '$' + '/'.join(str(x) for x in e.absolute_path) + ':', e.message[:130])
