import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
art = json.loads(
    (ROOT / "command-center/audit/AUD-0006-uncommitted-work-census.json").read_text(
        encoding="utf-8"
    )
)
rep = art["report"]
print("paths[0]:", json.dumps(rep["paths"][0], indent=2)[:800])
print()
print(
    "classifier_disagreements[0]:",
    json.dumps(rep["classifier_disagreements"][0], indent=2)[:900],
)
print()
keys = Counter()
for p in rep["paths"]:
    keys.update(p.keys())
print("paths[] key histogram:", dict(keys))
dkeys = Counter()
for d in rep["classifier_disagreements"]:
    dkeys.update(d.keys())
print("disagreement key histogram:", dict(dkeys))
print()
print("observations:")
for o in rep["observations"]:
    print("  -", json.dumps(o)[:400])
