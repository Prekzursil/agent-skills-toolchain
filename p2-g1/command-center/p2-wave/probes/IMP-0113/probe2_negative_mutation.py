"""IMP-0113 probe 2 (verifier): negative control + mutation. Disabling the
secret-gate makes composition_sets unequal and the missing rule id is exactly
secret-gate; the known-bad twin stays dirty while known-good stays silent
(both states); secret findings keep a 4-character prefix and withhold the
synthetic body.

Re-run: python command-center/p2-wave/probes/IMP-0113/probe2_negative_mutation.py
Exit 0 iff the mutation is visible and the redaction holds.
"""
import json
import re
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))
from marketplace.package_linter import RULE_IDS, composition_sets, lint_package  # noqa: E402

bad = W / "tools" / "marketplace" / "fixtures" / "known-bad"

full = composition_sets(bad)["rules"]
reduced = composition_sets(bad, enabled=[r for r in RULE_IDS if r != "secret-gate"])["rules"]
missing = set(full) - set(reduced)

report = lint_package(bad)
secret_rows = [f["detail"] for f in report["findings"] if f["rule"] == "secret-gate"]
prefix_ok = bool(secret_rows) and all(re.search(r"prefix '[^']{4}'", d) for d in secret_rows)
body_withheld = bool(secret_rows) and all("body withheld" in d for d in secret_rows)
no_full_secret = bool(secret_rows) and all("deadbeefcafe" not in d for d in secret_rows)

good = lint_package(W / "tools" / "marketplace" / "fixtures" / "known-good")
result = {
    "full_rules": sorted(full),
    "reduced_rules": sorted(reduced),
    "missing_after_disable": sorted(missing),
    "sets_unequal": set(full) != set(reduced),
    "missing_is_secret_gate": missing == {"secret-gate"},
    "secret_prefix_four": prefix_ok,
    "secret_body_withheld": body_withheld and no_full_secret,
    "known_good_silent": good["ok"] and not good["findings"],
    "unit_id": "IMP-0113",
}
result["pass"] = (
    result["sets_unequal"]
    and result["missing_is_secret_gate"]
    and result["secret_prefix_four"]
    and result["secret_body_withheld"]
    and result["known_good_silent"]
)
print(json.dumps(result, indent=1))
if result["pass"]:
    print("SUCCESS:IMP-0113-probe2 gate mutation visible; secret bodies withheld")
else:
    print("FAILED:IMP-0113-probe2")
sys.exit(0 if result["pass"] else 1)
