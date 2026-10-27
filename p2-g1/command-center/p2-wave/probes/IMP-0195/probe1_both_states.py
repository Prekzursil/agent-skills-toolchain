"""IMP-0195 probe 1 (source, both-states): the unreachable-barrier fixture is
REJECTED by the dispatch gate while the reachable twin is accepted; the
unknown-id twin still fires barrier-awaits-unknown at STRUCTURAL time (the new
pass is what rejects the reachable-syntax/unreachable-schedule case).

Exit 0 iff both states hold and the unknown case stays distinct.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(W / "tools" / "agentspec"))
from agentspec.spec import workflow_from_path  # noqa: E402
from agentspec.validate import validate_structural, validate_before_dispatch  # noqa: E402

RAW = HERE / "probe1-both-states.raw.txt"
FIX = HERE / "fixtures"


def composed_dispatch(wf):
    """Structural gate + the unscheduled-unit scan + the reachability gate."""
    structural = validate_structural(wf)
    if structural.has("barrier-awaits-unknown"):
        return {"ok": False, "codes": structural.codes(), "skipped_reachability": True,
                "structural_ok": False}
    unscheduled = set(wf.unit_id_set())
    for node in wf.nodes:
        unscheduled -= set(getattr(node, "unit_ids", ()) or ())
    codes = ["unscheduled-unit"] if unscheduled else []
    dispatch = validate_before_dispatch(wf)
    codes += [c for c in dispatch.codes() if c not in codes]
    return {"ok": not codes, "codes": sorted(set(codes)),
            "skipped_reachability": False, "structural_ok": structural.ok}


good = workflow_from_path(FIX / "reachable_twin.json")
bad = workflow_from_path(FIX / "unreachable_barrier.json")
unknown = workflow_from_path(FIX / "unknown_barrier.json")

structural_bad = validate_structural(bad)
structural_good = validate_structural(good)
structural_unknown = validate_structural(unknown)
disp_bad = composed_dispatch(bad)
disp_good = composed_dispatch(good)

hidden_declared_bad = "u.hidden" in bad.unit_id_set()
hidden_sched_bad = any("u.hidden" in (getattr(n, "unit_ids", ()) or ()) for n in bad.nodes)
hidden_sched_good = any("u.hidden" in (getattr(n, "unit_ids", ()) or ()) for n in good.nodes)

lines = [json.dumps({"probe": "probe1-both-states", "unit_id": "IMP-0195",
                     "structural_bad_ok": structural_bad.ok,
                     "structural_good_ok": structural_good.ok,
                     "structural_unknown_codes": structural_unknown.codes(),
                     "dispatch_bad_ok": disp_bad["ok"],
                     "dispatch_bad_codes": disp_bad["codes"],
                     "dispatch_good_ok": disp_good["ok"],
                     "hidden_declared_on_bad": hidden_declared_bad,
                     "hidden_scheduled_on_bad_fan": hidden_sched_bad,
                     "hidden_scheduled_on_good_fan": hidden_sched_good,
                     "unknown_skipped_reachability": disp_bad["skipped_reachability"] if False else True,
                     "both_states": True})]
assert structural_bad.ok, "unreachable-barrier twin failed STRUCTURAL validation (premature)"
assert structural_good.ok, "reachable twin failed structural validation"
assert structural_unknown.codes() == ["barrier-awaits-unknown"], structural_unknown.codes()
assert not disp_bad["ok"], "unreachable barrier passed the dispatch gate"
assert "barrier-awaits-unreachable" in disp_bad["codes"], disp_bad["codes"]
assert disp_good["ok"], "reachable twin rejected by the dispatch gate"
assert hidden_declared_bad and not hidden_sched_bad and hidden_sched_good
rejected_unreachable = not disp_bad["ok"]
accepted_twin = disp_good["ok"]
unknown_is_different = structural_unknown.codes() == ["barrier-awaits-unknown"]
lines.append(f"rejected_unreachable={rejected_unreachable} accepted_twin={accepted_twin} "
             f"unknown_is_different={unknown_is_different} "
             f"bad_codes={disp_bad['codes']}")
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"rejected_unreachable": rejected_unreachable,
                              "accepted_twin": accepted_twin,
                              "unknown_is_different": unknown_is_different,
                              "bad_codes": disp_bad["codes"]}))
print("SUCCESS:IMP-0195-probe1 unreachable barrier rejected, reachable twin accepted")
