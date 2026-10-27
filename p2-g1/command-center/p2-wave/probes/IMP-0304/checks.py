"""Shared IMP-0304 checks used by named probes and the receipt emitter."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.vote.weights import (  # noqa: E402
    constructed_fixtures,
    detect_cycles,
    expected_effective_fixtures,
    property_conservation,
    random_delegation_graph,
    resolve_drop_cyclic_bloc,
    resolve_weights,
    reverse_sink_map,
    total_power,
)

RECEIPT_REL = "command-center/receipts/IMP-0304.json"
MODULE_REL = "tools/council/vote/weights.py"
SENTINEL = "SUCCESS:IMP-0304"
REQUIRED_RECEIPT_FIELDS = (
    "unit_id",
    "artifact_paths",
    "spec_anchor",
    "evidence",
    "test_ids",
    "negative_control_ids",
    "reviewer_verdict",
    "residual_unknowns",
)

EXPECTED_CYCLES: dict[str, set[tuple[str, ...]]] = {
    "three_cycle": {("A", "B", "C")},
    "two_cycle": {("A", "B")},
    "self_loop": {("A",)},
    "inbound_to_cycle": {("A", "B", "C")},
    "dag_chain": set(),
    "two_disjoint_cycles": {("A", "B"), ("C", "D")},
    "chain_into_cycle": {("A", "B")},
    "authority_roles": set(),
}


def _fail(msg: str) -> dict[str, Any]:
    return {"pass": False, "error": msg}


def check_conservation_property() -> dict[str, Any]:
    result = property_conservation(n_trials=100, seed=20260824)
    if result["n_trials"] != 100:
        return _fail(f"expected 100 trials, got {result['n_trials']}")
    if result["n_fail"] != 0:
        bad = [r for r in result["rows"] if not r["conserved"]][:3]
        return _fail(f"conservation failed on {result['n_fail']} graphs sample={bad}")
    if not result["pass"]:
        return _fail("property_conservation pass flag is false")
    if result["n_cyclic_graphs"] < 1:
        return _fail("random suite produced zero cyclic graphs; seed not stressing cycles")
    return {
        "pass": True,
        "n_trials": result["n_trials"],
        "n_cyclic_graphs": result["n_cyclic_graphs"],
        "n_fail": 0,
        "seed": result["seed"],
        "first_row": result["rows"][0],
        "a_cyclic_row": next(r for r in result["rows"] if r["n_cycles"] > 0),
    }


def check_fixture_conservation_and_effective() -> dict[str, Any]:
    fixtures = constructed_fixtures()
    expected = expected_effective_fixtures()
    rows = []
    for name, graph in fixtures.items():
        res = resolve_weights(graph)
        authority, _ = graph.as_maps()
        before = total_power(authority)
        if (
            not res.conserved
            or res.total_power_before != before
            or res.total_power_after != before
        ):
            return _fail(
                f"{name}: conservation broken before={before} "
                f"reported=({res.total_power_before},{res.total_power_after})"
            )
        want = expected[name]
        if res.effective != want:
            return _fail(f"{name}: effective {res.effective} != hand-computed {want}")
        rows.append(
            {
                "name": name,
                "before": before,
                "after": res.total_power_after,
                "effective": res.effective,
                "n_cycles": len(res.cycle_report.cycles),
            }
        )
    return {"pass": True, "fixtures": rows}


def check_cycle_detection() -> dict[str, Any]:
    fixtures = constructed_fixtures()
    rows = []
    for name, graph in fixtures.items():
        report = detect_cycles(graph)
        got = set(report.cycles)
        want = EXPECTED_CYCLES[name]
        if got != want:
            return _fail(f"{name}: cycles {sorted(got)} != {sorted(want)}")
        expect_found = bool(want)
        if report.found != expect_found:
            return _fail(f"{name}: found={report.found} want={expect_found}")
        if expect_found and not report.cyclic_seats:
            return _fail(f"{name}: cycle found but cyclic_seats empty")
        if not expect_found and report.voided_edges:
            return _fail(f"{name}: DAG voided edges {report.voided_edges}")
        rows.append(
            {
                "name": name,
                "cycles": [list(c) for c in report.cycles],
                "cyclic_seats": sorted(report.cyclic_seats),
                "voided_edges": [list(e) for e in sorted(report.voided_edges)],
                "sccs_cyclic": [list(s) for s in report.sccs_cyclic],
            }
        )
    return {"pass": True, "fixtures": rows}


def check_resolution_policy_inbound_not_dropped() -> dict[str, Any]:
    graph = constructed_fixtures()["inbound_to_cycle"]
    res = resolve_weights(graph)
    if res.effective.get("A") != 5:
        return _fail(f"inbound 4 from D did not land on A: {res.effective}")
    if res.effective.get("D") != 0:
        return _fail(f"D should have delegated away, got {res.effective}")
    if res.silent_disenfranchisement:
        return _fail("production resolver flagged silent disenfranchisement")
    if not res.cycle_report.found:
        return _fail("inbound_to_cycle produced no cycle report")
    return {
        "pass": True,
        "effective": res.effective,
        "cycles": [list(c) for c in res.cycle_report.cycles],
        "policy": res.policy,
    }


def check_independent_reverse_flood() -> dict[str, Any]:
    rows = []
    for name, graph in constructed_fixtures().items():
        res = resolve_weights(graph)
        authority, _ = graph.as_maps()
        independent = reverse_sink_map(authority.keys(), res.remaining_delegations)
        if independent != res.sink_of:
            return _fail(
                f"{name}: reverse flood sink_of {independent} != forward {res.sink_of}"
            )
        indep_effective = {seat: 0 for seat in authority}
        for origin, weight in authority.items():
            indep_effective[independent[origin]] += weight
        if indep_effective != res.effective:
            return _fail(f"{name}: reverse effective {indep_effective} != {res.effective}")
        rows.append({"name": name, "sink_of": res.sink_of, "match": True})

    rng = random.Random(7)
    n_random_ok = 0
    for _ in range(20):
        g = random_delegation_graph(rng, rng.randint(3, 10), 0.55)
        res = resolve_weights(g)
        authority, _ = g.as_maps()
        independent = reverse_sink_map(authority.keys(), res.remaining_delegations)
        if independent != res.sink_of:
            return _fail(f"random reverse mismatch {independent} vs {res.sink_of}")
        n_random_ok += 1
    return {"pass": True, "fixtures": rows, "random_checked": n_random_ok}


def check_negative_control_mutant_fails_conservation() -> dict[str, Any]:
    graph = constructed_fixtures()["three_cycle"]
    good = resolve_weights(graph)
    bad = resolve_drop_cyclic_bloc(graph)
    if not good.conserved:
        return _fail("production three_cycle was not conserved; cannot attribute mutant")
    if bad.conserved:
        return _fail(
            "negative control did not fire: mutant conserved "
            f"before={bad.total_power_before} after={bad.total_power_after}"
        )
    if bad.total_power_after != 0:
        return _fail(f"mutant should drop the whole 3-cycle bloc, after={bad.total_power_after}")
    if bad.total_power_before != 6:
        return _fail(f"three_cycle before should be 6, got {bad.total_power_before}")
    if bad.total_power_before == bad.total_power_after:
        return _fail("property test unexpectedly passed on the mutant")

    inbound_bad = resolve_drop_cyclic_bloc(constructed_fixtures()["inbound_to_cycle"])
    if inbound_bad.conserved or inbound_bad.total_power_after != 0:
        return _fail(
            "mutant should also drop inbound-to-cycle power "
            f"after={inbound_bad.total_power_after} conserved={inbound_bad.conserved}"
        )
    dag_bad = resolve_drop_cyclic_bloc(constructed_fixtures()["dag_chain"])
    if not dag_bad.conserved:
        return _fail("mutant must stay silent on a DAG (no cycle to drop)")
    return {
        "pass": True,
        "production_three_cycle_conserved": True,
        "mutant_three_cycle_conserved": False,
        "mutant_before": bad.total_power_before,
        "mutant_after": bad.total_power_after,
        "property_assertion_on_mutant": "FAIL",
        "inbound_mutant_after": inbound_bad.total_power_after,
        "dag_mutant_conserved": True,
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
    }


def check_receipt() -> dict[str, Any]:
    path = REPO / RECEIPT_REL
    if not path.is_file() or path.stat().st_size <= 0:
        return _fail(f"receipt missing: {RECEIPT_REL}")
    text = path.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return _fail(f"receipt unparseable: {exc}")
    if not isinstance(doc, dict):
        return _fail("receipt is not an object")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"receipt self-declared {st}")
    if SENTINEL not in text:
        return _fail("sentinel SUCCESS:IMP-0304 absent")
    missing = [k for k in REQUIRED_RECEIPT_FIELDS if k not in doc]
    if missing:
        return _fail(f"receipt missing fields {missing}")
    if doc.get("unit_id") != "IMP-0304":
        return _fail(f"unit_id {doc.get('unit_id')!r}")
    raw_paths = doc.get("artifact_paths")
    if not isinstance(raw_paths, list) or not raw_paths:
        return _fail("artifact_paths empty")
    paths: list[str] = []
    for item in raw_paths:
        if isinstance(item, str):
            paths.append(item)
        elif isinstance(item, dict):
            paths.append(str(item.get("path") or ""))
    if MODULE_REL not in paths:
        return _fail(f"{MODULE_REL} not in artifact_paths")
    if RECEIPT_REL not in paths:
        return _fail(f"{RECEIPT_REL} not in artifact_paths")
    if str(doc.get("reviewer_verdict") or "").upper() not in {"PASS", "ACCEPT"}:
        return _fail(f"reviewer_verdict {doc.get('reviewer_verdict')!r} not PASS")
    return {
        "pass": True,
        "state": doc.get("state"),
        "sentinel_present": True,
        "bytes": path.stat().st_size,
    }


def run_probe1_body(*, require_receipt: bool) -> dict[str, Any]:
    parts = {
        "conservation_100": check_conservation_property(),
        "fixture_effective": check_fixture_conservation_and_effective(),
        "inbound_not_dropped": check_resolution_policy_inbound_not_dropped(),
    }
    ok = all(v.get("pass") for v in parts.values())
    if require_receipt:
        rec = check_receipt()
        parts["receipt"] = rec
        ok = ok and rec.get("pass") is True
    return {"pass": ok, "checks": parts}


def run_probe2_body() -> dict[str, Any]:
    parts = {
        "cycle_detection": check_cycle_detection(),
        "independent_reverse_flood": check_independent_reverse_flood(),
        "negative_control": check_negative_control_mutant_fails_conservation(),
    }
    ok = all(v.get("pass") for v in parts.values())
    return {"pass": ok, "checks": parts}
