import json
import os
import random

REPO = r"C:\Users\Prekzursil\p2-g1"
cat = json.load(open(REPO + r"\command-center\WORK-UNIT-CATALOG.json", encoding="utf-8"))
units = {x["id"]: x for x in cat["work_units"]}
cens = json.load(open(REPO + r"\_reviewer-w4-shard6-r2\census_out.json", encoding="utf-8"))
det = cens["detail"]
bf = [u for u, x in det.items() if x.get("B") is False]
print("B_fail count:", len(bf))
random.seed(7)
for uid in random.sample(bf, 5):
    e = units[uid]
    op = str(e["output_path"]).replace("\\", "/")
    print("---", uid, "state:", det[uid].get("state"), "out:", op)
    p = REPO + r"\command-center\p2-wave\probes" + "\\" + uid + r"\UNIT-ARTIFACT-MANIFEST.json"
    print("   probes-dir manifest exists:", os.path.isfile(p))
    print("   artifact exists:", os.path.isfile(os.path.join(REPO, op.replace("/", os.sep))))
