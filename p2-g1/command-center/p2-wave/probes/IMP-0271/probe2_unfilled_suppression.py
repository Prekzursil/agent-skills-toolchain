"""IMP-0271 probe 2: suppressing the unfilled-class report FAILS the census.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0271/probe2_unfilled_suppression.py
Exit 0 iff, on the live select_stakeholder module: the honest under-represented
run passes census_check with its unfilled_report present; the same run with the
report dropped (None), emptied ([]), or renamed to the wrong class FAILS
census_check with reason UNFILLED_REPORT_SUPPRESSED; a fully-represented run
passes with an empty report (silent-on-good control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "participants"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures import MIXES  # type: ignore  # noqa: E402
from select_stakeholder import REASON_OK, REASON_SUPPRESSED, census_check, select  # type: ignore  # noqa: E402

mix4 = next(m for m in MIXES if m["id"] == "MIX-4-unfillable-regulator")
mix1 = next(m for m in MIXES if m["id"] == "MIX-1-balanced-target")

honest = select(mix4["pool"], **mix4["select"])
good_run = select(mix1["pool"], **mix1["select"])

suppressed_none = dict(honest)
suppressed_none["unfilled_report"] = None
suppressed_empty = dict(honest)
suppressed_empty["unfilled_report"] = []
suppressed_renamed = dict(honest)
suppressed_renamed["unfilled_report"] = [
    {**u, "stakeholder_class": "operator"} for u in honest["unfilled_report"]
]

r_honest = census_check(honest)
r_none = census_check(suppressed_none)
r_empty = census_check(suppressed_empty)
r_renamed = census_check(suppressed_renamed)
r_good = census_check(good_run)

checks = {
    "honest_under_represented_passes": r_honest["ok"] is True and r_honest["reason"] == REASON_OK,
    "dropped_report_fails": r_none["ok"] is False and r_none["reason"] == REASON_SUPPRESSED,
    "emptied_report_fails": r_empty["ok"] is False and r_empty["reason"] == REASON_SUPPRESSED,
    "renamed_report_fails": r_renamed["ok"] is False and r_renamed["reason"] == REASON_SUPPRESSED,
    "good_state_silent": r_good["ok"] is True and r_good["reason"] == REASON_OK and r_good["short"] == [],
    "short_names_regulator": r_honest["short"] == ["regulator"],
}
both_states = {
    "fired_on_bad_state": not (r_none["ok"] and r_empty["ok"] and r_renamed["ok"]),
    "silent_on_good_state": r_honest["ok"] and r_good["ok"],
}
ok = all(checks.values()) and all(both_states.values())
out = {"probe": "probe2-unfilled-suppression", "unit_id": "IMP-0271",
       "honest_reason": r_honest["reason"], "short": r_honest["short"],
       "suppressed_reasons": [r_none["reason"], r_empty["reason"], r_renamed["reason"]],
       "both_states": both_states,
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe2-unfilled.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0271-probe2 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0271-probe2 suppressed unfilled report FAILS census; honest report passes")
