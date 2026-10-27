"""IMP-0113 probe 1 (source): on the known-bad fixture the linter finding set
equals the union of the six standalone sub-checks, and that union is exactly
the six rule ids. The known-good fixture yields zero findings from the linter
AND from every standalone sub-check in the same run.

Re-run: python command-center/p2-wave/probes/IMP-0113/probe1_composition.py
Exit 0 iff composition == union == six rule ids and known-good is clean.
"""
import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))
from marketplace.checks import RULE_IDS, SUBCHECKS  # noqa: E402
from marketplace.package_linter import lint_package  # noqa: E402

bad = W / "tools" / "marketplace" / "fixtures" / "known-bad"
good = W / "tools" / "marketplace" / "fixtures" / "known-good"

composer_bad = lint_package(bad)
composer_ids = set(composer_bad["rule_ids"])
union_ids = set()
for rule_id in RULE_IDS:
    for row in SUBCHECKS[rule_id](bad):
        union_ids.add(str(row.get("rule") or rule_id))

good_report = lint_package(good)
good_standalone = {rid: SUBCHECKS[rid](good) for rid in RULE_IDS}

result = {
    "composer_rule_ids": sorted(composer_ids),
    "union_rule_ids": sorted(union_ids),
    "composition_equals_union": composer_ids == union_ids,
    "six_rule_ids": sorted(RULE_IDS),
    "union_exactly_six": union_ids == set(RULE_IDS),
    "known_good_linter_ok": good_report["ok"],
    "known_good_standalone_clean": all(not v for v in good_standalone.values()),
    "unit_id": "IMP-0113",
}
result["pass"] = (
    result["composition_equals_union"]
    and result["union_exactly_six"]
    and result["known_good_linter_ok"]
    and result["known_good_standalone_clean"]
)
print(json.dumps(result, indent=1))
if result["pass"]:
    print("SUCCESS:IMP-0113-probe1 composition equals union of six standalone checks")
else:
    print("FAILED:IMP-0113-probe1")
sys.exit(0 if result["pass"] else 1)
