"""IMP-0099 probe 2 (verifier): the IMP-0070 comparator engine on the range
">=1.0.0 <1.2.3" reproduces every matrix verdict (independent instrument);
the negative control flags demo-kit@1.1.0 while demo-kit@1.2.3 and
sibling-kit@1.1.0 stay installable; an open-ended range cannot silently
mark every future version.

Re-run: python command-center/p2-wave/probes/IMP-0099/probe2_independent_engine.py
Exit 0 iff comparator parity, negative control and open-ended gate all hold.
"""
import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))
from marketplace.advisory import OpenEndedUndisclosedError, evaluate_installed, from_record  # noqa: E402
from marketplace.version import satisfies  # noqa: E402

fixture = json.loads(
    (W / "tools" / "marketplace" / "fixtures" / "imp0099_matrix.json").read_text(encoding="utf-8")
)
rng = fixture["imp0070_range"]
mismatched = []
for case in fixture["cases"]:
    engine = satisfies(case["version"], rng)
    if engine is not bool(case["expected_affected"]):
        mismatched.append({"id": case["id"], "version": case["version"], "engine": engine})

adv = from_record(fixture["advisory"])
neg = fixture["negative_control"]
hit = evaluate_installed(fixture["package"], neg["affected_package_version"], [adv])
sib_ver = evaluate_installed(fixture["package"], neg["unaffected_sibling_version"], [adv])
sib_pkg = evaluate_installed(fixture["sibling_package"], neg["unaffected_sibling_package_version"], [adv])

open_ended_disclosed = fixture.get("open_ended_advisory") or {
    "identifier": "GHSA-open-0002",
    "package": fixture["package"],
    "affected_version_ranges": [{"introduced": "1.0.0"}],
    "unbounded_future_disclosed": True,
}
open_ended = {k: v for k, v in open_ended_disclosed.items() if k != "unbounded_future_disclosed"}
refused = ""
try:
    from_record(open_ended)
except OpenEndedUndisclosedError as exc:
    refused = str(exc)
disclosed_adv = from_record(open_ended_disclosed)
future = evaluate_installed(fixture["package"], "99.0.0", [disclosed_adv])

result = {
    "range": rng,
    "comparator_mismatches": mismatched,
    "comparator_parity": not mismatched,
    "negative_control": {
        "hit_affected": hit.affected,
        "hit_installable": hit.installable,
        "sibling_version_installable": sib_ver.installable,
        "sibling_package_installable": sib_pkg.installable,
    },
    "open_ended_refusal": refused,
    "disclosed_future_hit": {
        "affected": future.affected,
        "open_ended_hits": future.open_ended_hits,
        "notes": future.notes,
    },
    "unit_id": "IMP-0099",
}
result["pass"] = (
    result["comparator_parity"]
    and result["negative_control"]["hit_affected"]
    and not result["negative_control"]["hit_installable"]
    and result["negative_control"]["sibling_version_installable"]
    and result["negative_control"]["sibling_package_installable"]
    and bool(result["open_ended_refusal"])
    and result["disclosed_future_hit"]["affected"]
    and result["disclosed_future_hit"]["open_ended_hits"]
)
print(json.dumps(result, indent=1))
if result["pass"]:
    print("SUCCESS:IMP-0099-probe2 comparator parity + negative control + open-ended gate")
else:
    print("FAILED:IMP-0099-probe2")
sys.exit(0 if result["pass"] else 1)
