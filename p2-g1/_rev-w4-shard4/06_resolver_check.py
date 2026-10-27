import json
import sys
from pathlib import Path

REPO = Path(r'C:/Users/Prekzursil/p2-g1')
MINE = ["AUD-0044", "AUD-0047", "AUD-0053", "AUD-0055", "AUD-0057",
        "AUD-0064", "AUD-0066", "AUD-0069", "AUD-0071", "AUD-0072",
        "AUD-0075", "AUD-0080"]

sys.path.insert(0, str(REPO / 'platform' / 'lib'))
import importlib.util
spec = importlib.util.spec_from_file_location('schema_resolver', REPO / 'platform' / 'lib' / 'schema_resolver.py')
mod = importlib.util.module_from_spec(spec)
sys.modules['schema_resolver'] = mod
spec.loader.exec_module(mod)

cat = json.loads((REPO / 'command-center/WORK-UNIT-CATALOG.json').read_text(encoding='utf-8'))
byid = {e['id']: e for e in cat['work_units']}
res = {}
for uid in MINE:
    e = byid[uid]
    out_rel = str(e['output_path']).replace('\\', '/')
    p = REPO / out_rel
    doc = json.loads(p.read_text(encoding='utf-8'))
    try:
        errs = mod.validate_artifact(doc, e['output_schema'])
    except Exception as ex:
        errs = [f'RESOLVER-EXCEPTION {type(ex).__name__}: {str(ex)[:150]}']
    res[uid] = {'schema': e['output_schema'], 'n_errors': len(errs), 'errors': errs[:6]}
    print(f'{uid}: {len(errs)} errors')
    for x in errs[:6]:
        print('   -', x[:150])
Path(__file__).parent.joinpath('resolver-results.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
