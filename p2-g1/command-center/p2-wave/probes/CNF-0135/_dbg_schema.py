import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shard4_w1"))
import lib_shard4 as L
doc = json.loads((L.REPO / "command-center/receipts/CNF-0135.json").read_text(encoding="utf-8"))
errs = L.validate(doc, "command-center/schema/discrepancy-ledger.schema.json")
print("ERRCOUNT", len(errs))
for e in errs:
    print("FULLERR:", str(e))
