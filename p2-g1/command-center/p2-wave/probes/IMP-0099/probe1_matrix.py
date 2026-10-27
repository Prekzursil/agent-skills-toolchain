"""IMP-0099 probe 1 (source): the 20-case version matrix on GHSA-demo-0001
(introduced 1.0.0, fixed 1.2.3) yields the expected affected/unaffected
verdicts -- including at-fixed (unaffected) and prerelease-of-fixed (affected).

Re-run: python command-center/p2-wave/probes/IMP-0099/probe1_matrix.py
Exit 0 iff 20/20 cases match the fixture expectations.
"""
import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))
from marketplace.advisory import from_record, is_affected  # noqa: E402

fixture = json.loads(
    (W / "tools" / "marketplace" / "fixtures" / "imp0099_matrix.json").read_text(encoding="utf-8")
)
adv = from_record(fixture["advisory"])
results = []
failed = []
for case in fixture["cases"]:
    got = is_affected(adv, case["version"])
    ok = got is bool(case["expected_affected"])
    results.append(
        {"id": case["id"], "version": case["version"], "locus": case["locus"],
         "expected": bool(case["expected_affected"]), "got": got, "ok": ok}
    )
    if not ok:
        failed.append(case["id"])
result = {
    "advisory": adv.identifier,
    "cases": len(fixture["cases"]),
    "passed": len(fixture["cases"]) - len(failed),
    "failed": failed,
    "results": results,
    "unit_id": "IMP-0099",
}
result["pass"] = not failed and result["cases"] == 20
print(json.dumps(result, indent=1))
if result["pass"]:
    print("SUCCESS:IMP-0099-probe1 20/20 matrix verdicts match")
else:
    print("FAILED:IMP-0099-probe1")
sys.exit(0 if result["pass"] else 1)
