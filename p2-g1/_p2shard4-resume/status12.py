import sys, json
from pathlib import Path
REPO = Path.home() / "p2-g1"
sys.path.insert(0, str(REPO / "command-center/p2-wave/probes/_shard4_w1"))
import lib_shard4 as L

BS = chr(92)
mine = ['BLD-0052','BLD-0057','CC-0011','CC-0017','CC-0022','CC-0024','CNF-0063','CNF-0120','CNF-0135','CNF-0141','CNF-0144','CNF-0157']
for uid in mine:
    e = L.cat_entry(uid)
    out = L.REPO / e['output_path'].replace(BS, '/')
    if not out.is_file():
        print(f"{uid}: ARTIFACT MISSING at {e['output_path']}")
        continue
    try:
        doc = json.loads(out.read_text(encoding='utf-8'))
    except Exception as ex:
        print(f"{uid}: UNPARSEABLE {ex}")
        continue
    errs = L.validate(doc, e['output_schema'].replace(BS, '/'))
    print(f"{uid}: state={doc.get('state')} errors={len(errs)}")
    for er in errs[:6]:
        print("   ", str(er)[:180])
