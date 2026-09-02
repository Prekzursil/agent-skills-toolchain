#!/usr/bin/env python3
"""Probe 1: unreachable-barrier REJECTED; reachable twin ACCEPTED (both-states).

Also proves barrier-awaits-unknown is a different structural defect: the hidden
unit in the unreachable fixture is declared, so structural validation passes.
"""

from __future__ import annotations

import json

from paths import FIXDIR

from agentspec.spec import workflow_from_path
from agentspec.validate import validate_before_dispatch, validate_structural


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0195-probe1 {msg}")
    return 1


def main() -> int:
    good = workflow_from_path(FIXDIR / "reachable_twin.json")
    bad = workflow_from_path(FIXDIR / "unreachable_barrier.json")
    unknown = workflow_from_path(FIXDIR / "unknown_barrier.json")

    st_good = validate_structural(good)
    st_bad = validate_structural(bad)
    st_unknown = validate_structural(unknown)
    disp_good = validate_before_dispatch(good)
    disp_bad = validate_before_dispatch(bad)
    disp_unknown = validate_before_dispatch(unknown)

    # Twin delta is only which units the reachable FanOut schedules.
    good_fan = next(n for n in good.nodes if n.id == "fan")
    bad_fan = next(n for n in bad.nodes if n.id == "fan")
    good_join = next(n for n in good.nodes if n.id == "join")
    bad_join = next(n for n in bad.nodes if n.id == "join")
    if good.unit_id_set() != bad.unit_id_set():
        return _fail("twin unit sets differ; fixtures are not twins")
    if good_join.await_unit_ids != bad_join.await_unit_ids:
        return _fail("twin barriers await different sets")
    if "u.hidden" not in bad.unit_id_set():
        return _fail("unreachable fixture must declare u.hidden so it is not unknown")
    if "u.hidden" in bad_fan.unit_ids:
        return _fail("bad fanout still schedules u.hidden; defect not planted")
    if "u.hidden" not in good_fan.unit_ids:
        return _fail("good fanout does not schedule u.hidden; twin is not the repair")

    if not st_good.ok:
        return _fail(f"reachable twin failed structural: {st_good.as_dict()}")
    if not st_bad.ok:
        return _fail(
            f"unreachable fixture failed structural (must be known-id): {st_bad.as_dict()}"
        )
    if st_bad.has("barrier-awaits-unknown"):
        return _fail("planted unreachable await was misclassified as unknown")
    if not st_unknown.has("barrier-awaits-unknown"):
        return _fail(f"unknown fixture did not fire barrier-awaits-unknown: {st_unknown.as_dict()}")
    if st_unknown.has("barrier-awaits-unreachable"):
        return _fail("unknown fixture must not be classified as unreachable")
    if disp_unknown.reachability is not None:
        return _fail("unknown fixture must fail closed at structural and skip reachability")

    if disp_good.ok is not True:
        return _fail(f"reachable twin was REJECTED: {disp_good.as_dict()}")
    if disp_good.has("barrier-awaits-unreachable"):
        return _fail("reachable twin incorrectly flagged unreachable barrier")
    if disp_bad.ok is not False:
        return _fail(f"unreachable-barrier fixture was ACCEPTED: {disp_bad.as_dict()}")
    if not disp_bad.has("barrier-awaits-unreachable"):
        return _fail(
            f"unreachable fixture REJECTED but not as barrier-awaits-unreachable: {disp_bad.as_dict()}"
        )
    if not disp_bad.has("orphan-barrier"):
        return _fail("orphan-barrier not reported on the planted await")

    report = {
        "structural_good_ok": st_good.ok,
        "structural_bad_ok": st_bad.ok,
        "structural_unknown_codes": list(st_unknown.codes()),
        "dispatch_good_ok": disp_good.ok,
        "dispatch_bad_ok": disp_bad.ok,
        "dispatch_bad_codes": list(disp_bad.codes()),
        "unknown_skipped_reachability": disp_unknown.reachability is None,
        "hidden_declared_on_bad": "u.hidden" in bad.unit_id_set(),
        "hidden_scheduled_on_bad_fan": "u.hidden" in bad_fan.unit_ids,
        "hidden_scheduled_on_good_fan": "u.hidden" in good_fan.unit_ids,
        "both_states": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "rejected_unreachable=True accepted_twin=True unknown_is_different=True "
        f"bad_codes={list(disp_bad.codes())}"
    )
    print("SUCCESS:IMP-0195-probe1 unreachable-barrier both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
