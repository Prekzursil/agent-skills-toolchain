"""Chaos, resume, coverage, and vacuity cases for ARC-0036."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from predicate import CONDITION_TEXT, batch_complete
from runtime import (
    World,
    corrupt_ledger,
    duplicate_dispatch,
    exit_zero_alone,
    inject_condition,
    kill_monitor,
    kill_worker,
    naive_claim_means_complete,
    run_healthy,
    unstarted,
    vacuity,
)

NAMED_CHAOS = [
    {
        "id": "CHAOS-KILL-MONITOR",
        "catalog_name": "kill the monitor mid-run",
        "injection_mechanism": (
            "Worker writes a schema-valid artifact and a WORKER-EXIT SUCCESS "
            "ledger record; the monitor process is then killed before HARVEST "
            "and before MANIFEST registration."
        ),
        "target_condition": 11,
        "assertion": (
            "Shared reducer returns INCOMPLETE with C11 UNSATISFIED "
            "(output was not registered in the artifact manifest)."
        ),
        "expected_verdict": "INCOMPLETE",
    },
    {
        "id": "CHAOS-KILL-WORKER",
        "catalog_name": "kill a worker mid-unit",
        "injection_mechanism": (
            "Worker is SIGKILL-equivalent after creating a 1-byte torn artifact "
            "('{') and before a valid terminal write."
        ),
        "target_condition": 3,
        "assertion": (
            "Shared reducer returns INCOMPLETE with C3 UNSATISFIED "
            "(artifact below the 128-byte meaningful-size floor)."
        ),
        "expected_verdict": "INCOMPLETE",
    },
    {
        "id": "CHAOS-CORRUPT-LEDGER",
        "catalog_name": "corrupt a ledger record",
        "injection_mechanism": (
            "After a committed HARVEST line exists, that JSONL line is "
            "overwritten in place with a torn JSON prefix. Resume must parse "
            "the ledger record against ledger.schema.json."
        ),
        "target_condition": 4,
        "assertion": (
            "Shared reducer returns INCOMPLETE with C4 UNSATISFIED "
            "(torn ledger record does not parse against its schema)."
        ),
        "expected_verdict": "INCOMPLETE",
    },
    {
        "id": "CHAOS-DUP-DISPATCH",
        "catalog_name": "replay a duplicate dispatch",
        "injection_mechanism": (
            "Two dispatchers append CLAIM records for the same unit_id with "
            "no exclusive lock. Both proceed; claim_count becomes 2."
        ),
        "target_condition": 1,
        "assertion": (
            "Shared reducer returns INCOMPLETE with C1 UNSATISFIED "
            "(no exclusive valid terminal / winner)."
        ),
        "expected_verdict": "INCOMPLETE",
    },
    {
        "id": "CHAOS-PARTIAL-BATCH",
        "catalog_name": "resume from a partial batch",
        "injection_mechanism": (
            "Batch of three units: only the first is harvested. Resume "
            "re-reads the ledger and re-evaluates every member. Unfinished "
            "members still have no artifact."
        ),
        "target_condition": 2,
        "assertion": (
            "Fan-in reducer returns INCOMPLETE because unfinished members "
            "fail C2; a naive claim-means-complete reducer wrongly returns "
            "COMPLETE and is rejected."
        ),
        "expected_verdict": "INCOMPLETE",
    },
]


def _summarize(case_id: str, spec: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    target = int(spec["target_condition"])
    rows = result.get("conditions") or []
    target_row = next((r for r in rows if r["n"] == target), None)
    outcomes = {r["id"]: r["outcome"] for r in rows}
    unsatisfied = [r["n"] for r in rows if r["outcome"] == "UNSATISFIED"]
    return {
        "id": case_id,
        "named_chaos": True,
        "catalog_name": spec["catalog_name"],
        "injection_mechanism": spec["injection_mechanism"],
        "target_condition": target,
        "target_id": f"C{target}",
        "assertion": spec["assertion"],
        "expected_verdict": spec["expected_verdict"],
        "verdict": result["verdict"],
        "complete": result.get("complete"),
        "failing_condition_ids": result.get("failing_condition_ids") or [],
        "target_unsatisfied": bool(
            target_row and target_row["outcome"] == "UNSATISFIED"
        ),
        "unsatisfied_ns": unsatisfied,
        "outcomes": outcomes,
        "unit_id": result.get("unit_id"),
    }


def _run_named(world: World) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_id = {c["id"]: c for c in NAMED_CHAOS}

    spec = by_id["CHAOS-KILL-MONITOR"]
    out.append(_summarize(spec["id"], spec, kill_monitor(world, "FIX-1011")))

    spec = by_id["CHAOS-KILL-WORKER"]
    out.append(_summarize(spec["id"], spec, kill_worker(world, "FIX-1003")))

    spec = by_id["CHAOS-CORRUPT-LEDGER"]
    out.append(_summarize(spec["id"], spec, corrupt_ledger(world, "FIX-1004")))

    spec = by_id["CHAOS-DUP-DISPATCH"]
    out.append(_summarize(spec["id"], spec, duplicate_dispatch(world, "FIX-1001")))

    spec = by_id["CHAOS-PARTIAL-BATCH"]
    a = run_healthy(world, "FIX-1021")
    b = unstarted(world, "FIX-1022")
    c = unstarted(world, "FIX-1023")
    members = [a["verdict"], b["verdict"], c["verdict"]]
    fanin = batch_complete(members)
    naive = all(
        naive_claim_means_complete(world, uid)
        for uid in ("FIX-1021", "FIX-1022", "FIX-1023")
    )
    # Fold the unfinished member (C2) into the case summary.
    row = _summarize(spec["id"], spec, b)
    row["verdict"] = fanin
    row["complete"] = fanin == "COMPLETE"
    row["batch_member_verdicts"] = members
    row["naive_claim_means_complete"] = naive
    row["naive_rejected"] = naive is True and fanin == "INCOMPLETE"
    row["failing_condition_ids"] = b.get("failing_condition_ids") or []
    out.append(row)
    return out


def _run_injectors(world: World) -> list[dict[str, Any]]:
    """Drive every condition that the five named chaos cases might miss."""
    named_targets = {c["target_condition"] for c in NAMED_CHAOS}
    extra: list[dict[str, Any]] = []
    for n in range(1, 13):
        if n in named_targets:
            continue
        uid = f"FIX-11{n:02d}"
        result = inject_condition(world, uid, n)
        spec = {
            "catalog_name": f"condition-injector C{n}",
            "injection_mechanism": (
                f"Start from a healthy unit and inject the C{n} failure only "
                f"({CONDITION_TEXT[n]})."
            ),
            "target_condition": n,
            "assertion": f"C{n} is UNSATISFIED and the reducer returns INCOMPLETE.",
            "expected_verdict": "INCOMPLETE",
        }
        row = _summarize(f"INJ-C{n}", spec, result)
        row["named_chaos"] = False
        extra.append(row)
    return extra


def coverage_from_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    exercised: set[int] = set()
    for case in cases:
        for n in case.get("unsatisfied_ns") or []:
            exercised.add(int(n))
    uncovered = []
    for n in range(1, 13):
        if n not in exercised:
            uncovered.append(
                {"n": n, "id": f"C{n}", "text": CONDITION_TEXT[n]}
            )
    total = 12
    n_ex = len(exercised)
    return {
        "exercised": n_ex,
        "total": total,
        "ratio": n_ex / total,
        "exercised_ids": [f"C{n}" for n in sorted(exercised)],
        "uncovered": uncovered,
        "basis": (
            "A condition is exercised iff at least one live case produced "
            "UNSATISFIED for that numbered condition (not UNKNOWN, not SATISFIED)."
        ),
    }


def run_all(root: Path | None = None) -> dict[str, Any]:
    cleanup = None
    if root is None:
        cleanup = tempfile.TemporaryDirectory(prefix="arc-0036-")
        root = Path(cleanup.name)
    try:
        world = World(root)
        healthy = run_healthy(world, "FIX-1000")
        named = _run_named(world)
        extra = _run_injectors(world)
        vac = vacuity(world, "FIX-1099")
        ez = exit_zero_alone(world, "FIX-1098")
        all_cases = named + extra
        # Vacuity also exercises C2; include its after-state in coverage.
        vac_unsat = [
            r["n"] for r in vac["after"]["conditions"] if r["outcome"] == "UNSATISFIED"
        ]
        all_for_coverage = all_cases + [
            {"unsatisfied_ns": vac_unsat, "id": "MUT-VACUITY-DELETE-ARTIFACT"}
        ]
        cov = coverage_from_cases(all_for_coverage)
        healthy_ok = healthy["verdict"] == "COMPLETE"
        named_ok = all(
            c["verdict"] == c["expected_verdict"] and c["target_unsatisfied"]
            for c in named
        )
        extra_ok = all(
            c["verdict"] == "INCOMPLETE" and c["target_unsatisfied"] for c in extra
        )
        vac_ok = (
            vac["flipped"] is True
            and vac["c2_after"] == "UNSATISFIED"
            and vac["before"]["verdict"] == "COMPLETE"
        )
        ez_ok = ez["verdict"] != "COMPLETE"
        partial = next(c for c in named if c["id"] == "CHAOS-PARTIAL-BATCH")
        naive_ok = partial.get("naive_rejected") is True
        return {
            "healthy": {
                "verdict": healthy["verdict"],
                "complete": healthy["complete"],
                "failing_condition_ids": healthy["failing_condition_ids"],
                "unknown_condition_ids": healthy.get("unknown_condition_ids") or [],
            },
            "named_chaos": named,
            "injectors": extra,
            "vacuity": {
                "before_verdict": vac["before"]["verdict"],
                "after_verdict": vac["after"]["verdict"],
                "flipped": vac["flipped"],
                "c2_after": vac["c2_after"],
                "deleted": vac["deleted"],
                "after_failing": vac["after"]["failing_condition_ids"],
            },
            "exit_zero_alone": {
                "verdict": ez["verdict"],
                "complete": ez.get("complete"),
                "failing_condition_ids": ez.get("failing_condition_ids") or [],
            },
            "coverage": cov,
            "pass": bool(
                healthy_ok
                and named_ok
                and extra_ok
                and vac_ok
                and ez_ok
                and naive_ok
                and cov["exercised"] == 12
                and cov["uncovered"] == []
            ),
            "checks": {
                "healthy_complete": healthy_ok,
                "named_chaos_target_unsatisfied": named_ok,
                "injectors_target_unsatisfied": extra_ok,
                "vacuity_flips_c2": vac_ok,
                "exit_zero_alone_not_complete": ez_ok,
                "partial_batch_rejects_naive": naive_ok,
                "coverage_12_of_12": cov["exercised"] == 12 and not cov["uncovered"],
            },
        }
    finally:
        if cleanup is not None:
            cleanup.cleanup()
