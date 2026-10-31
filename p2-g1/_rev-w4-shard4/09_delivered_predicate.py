import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(r'C:/Users/Prekzursil/p2-g1')
MINE = ["AUD-0044", "AUD-0047", "AUD-0053", "AUD-0055", "AUD-0057",
        "AUD-0064", "AUD-0066", "AUD-0069", "AUD-0071", "AUD-0072",
        "AUD-0075", "AUD-0080"]

spec = importlib.util.spec_from_file_location('ready_units', REPO / 'command-center' / 'ready_units.py')
ru = importlib.util.module_from_spec(spec)
sys.modules['ready_units'] = ru
spec.loader.exec_module(ru)

resolver = ru._load_resolver()
print('resolver loaded:', resolver is not None)
cat = json.loads((REPO / 'command-center/WORK-UNIT-CATALOG.json').read_text(encoding='utf-8'))
byid = {e['id']: e for e in cat['work_units']}
rows = {}
for uid in MINE:
    ok, why = ru.artifact_delivered(byid[uid], resolver)
    rows[uid] = {'delivered': ok, 'why': why}
    print(f"{uid}: delivered={ok} why={why}")
Path(__file__).parent.joinpath('delivered-predicate.json').write_text(json.dumps(rows, indent=1), encoding='utf-8')
