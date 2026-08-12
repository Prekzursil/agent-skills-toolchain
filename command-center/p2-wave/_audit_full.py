"""AUDIT (independent): full row text for the audited units + top-level shape of each artifact."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAT = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
by = {u["id"]: u for u in CAT["work_units"]}

for uid in ["IMP-0433", "AUD-0041", "AUD-0030"]:
    u = by[uid]
    print(f"================ {uid} ================")
    for k in ("title", "question_or_target", "inputs", "tests_required",
              "evidence_requirement", "completion_sentinel", "failure_classification"):
        print(f"--{k}--\n  {u.get(k)!r}")
    print()

print("################ ARTIFACT TOP-LEVEL SHAPES ################")
paths = {
    "IMP-0433": "command-center/receipts/IMP-0433.json",
    "AUD-0041": "command-center/audit/AUD-0041-ci-step-inventory.json",
    "AUD-0051": "command-center/audit/AUD-0051-coverage-baseline.json",
    "AUD-0030": "command-center/audit/AUD-0030-import-graph-cycles.json",
    "AUD-0020": "command-center/audit/AUD-0020-python-dep-inventory.json",
}
for uid, p in paths.items():
    d = json.loads((REPO / p).read_text(encoding="utf-8"))
    print(f"{uid}: keys={sorted(d.keys())}")
    print(f"   state={d.get('state')!r} sentinel={str(d.get('sentinel'))[:90]!r}")
