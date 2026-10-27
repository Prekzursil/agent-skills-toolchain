"""Proof harness for the CNF-0139 class-expansion trigger."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from class_expansion import evaluate_class, load_threshold


def _members(tag: str, n: int = 20) -> list[str]:
    return [f"CNF-0139-REV-{tag}-m{i:02d}" for i in range(1, n + 1)]


def both_states(repo: Path, root: Path) -> dict[str, Any]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    thr = load_threshold(repo)
    fire_q = root / "fire-queue.json"
    silent_q = root / "silent-queue.json"
    members = _members("synth-bad-plus-one")
    fire = evaluate_class(
        class_id="synth-bad-plus-one",
        members=members,
        n_fail=2,
        n_obs=10,
        queue_path=fire_q,
        threshold=thr,
    )
    silent = evaluate_class(
        class_id="synth-good-minus-one",
        members=_members("synth-good-minus-one"),
        n_fail=0,
        n_obs=10,
        queue_path=silent_q,
        threshold=thr,
    )
    ok = (
        fire["decision"] == "EXPAND"
        and silent["decision"] == "SILENT"
        and len(fire["created_unit_ids"]) == 20
        and fire["queue_length_delta"] == 20
        and silent["queue_length_delta"] == 0
    )
    return {"pass": ok, "fire": fire, "silent": silent}


def boundary(repo: Path, root: Path) -> dict[str, Any]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    thr = load_threshold(repo)
    at = evaluate_class(
        class_id="synth-at-threshold",
        members=_members("at-threshold"),
        n_fail=1,
        n_obs=10,
        queue_path=root / "at.json",
        threshold=thr,
    )
    above = evaluate_class(
        class_id="synth-above",
        members=_members("above"),
        n_fail=2,
        n_obs=10,
        queue_path=root / "above.json",
        threshold=thr,
    )
    ok = at["decision"] == "SILENT" and at["reason"] == "at_threshold" and above["decision"] == "EXPAND"
    return {
        "pass": ok,
        "at_threshold": at,
        "above": above,
        "specified_boundary": "1/10",
        "fraction_rule": "EXPAND iff rate > threshold; equality is SILENT",
    }


def antithrash(repo: Path, root: Path) -> dict[str, Any]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    thr = load_threshold(repo)
    q = root / "latch.json"
    expanded: set[str] = set()
    members = _members("antithrash")
    first = evaluate_class(
        class_id="synth-antithrash",
        members=members,
        n_fail=2,
        n_obs=10,
        queue_path=q,
        expanded=expanded,
        threshold=thr,
    )
    second = evaluate_class(
        class_id="synth-antithrash",
        members=members,
        n_fail=2,
        n_obs=10,
        queue_path=q,
        expanded=expanded,
        threshold=thr,
    )
    ok = (
        first["decision"] == "EXPAND"
        and first["queue_length_delta"] == 20
        and second["decision"] == "SILENT"
        and second["reason"] == "already_fully_expanded"
        and second["queue_length_delta"] == 0
    )
    return {"pass": ok, "first": first, "second": second}


def denominator_control(repo: Path, root: Path) -> dict[str, Any]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    thr = load_threshold(repo)
    correct = evaluate_class(
        class_id="synth-denom-correct",
        members=_members("denom-correct"),
        n_fail=2,
        n_obs=22,
        n_blocked=0,
        queue_path=root / "correct.json",
        threshold=thr,
        include_blocked_in_denominator=False,
    )
    # Counterfactual: counting 12 BLOCKED in the denominator (2/22) is SILENT;
    # excluding them (2/10) EXPANDS. The live trigger excludes BLOCKED.
    excluded = evaluate_class(
        class_id="synth-denom-excluded",
        members=_members("denom-excluded"),
        n_fail=2,
        n_obs=10,
        n_blocked=12,
        queue_path=root / "excluded.json",
        threshold=thr,
        include_blocked_in_denominator=False,
    )
    included = evaluate_class(
        class_id="synth-denom-included",
        members=_members("denom-included"),
        n_fail=2,
        n_obs=10,
        n_blocked=12,
        queue_path=root / "included.json",
        threshold=thr,
        include_blocked_in_denominator=True,
    )
    ok = excluded["decision"] == "EXPAND" and included["decision"] == "SILENT"
    return {
        "pass": ok,
        "correct": correct,
        "counterfactual_rate": "2/22",
        "counterfactual_would_expand": False,
        "decision_changes": ok,
        "note": "Relabeling REFUTED as BLOCKED and keeping them in the denominator silences 2/10 EXPAND.",
    }


def reviewer_slip_attempts(repo: Path, root: Path) -> dict[str, Any]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    thr = load_threshold(repo)
    at = evaluate_class(
        class_id="slip-at-threshold",
        members=_members("slip-at"),
        n_fail=1,
        n_obs=10,
        queue_path=root / "slip-at.json",
        threshold=thr,
    )
    blocked = evaluate_class(
        class_id="slip-blocked-in-denom",
        members=_members("slip-blocked"),
        n_fail=2,
        n_obs=10,
        n_blocked=12,
        queue_path=root / "slip-blocked.json",
        threshold=thr,
        include_blocked_in_denominator=True,
    )
    ok = at["decision"] == "SILENT" and blocked["decision"] == "SILENT"
    return {
        "pass": ok,
        "attempts": [
            {"id": "equality-at-threshold", "slipped": False, "decision": at["decision"]},
            {"id": "blocked-in-denominator", "slipped": False, "decision": blocked["decision"]},
        ],
        "verdict": "PASS" if ok else "FAIL",
    }


def run_all(repo: Path, proof_dir: Path) -> dict[str, Any]:
    proof_dir = Path(proof_dir)
    proof_dir.mkdir(parents=True, exist_ok=True)
    both = both_states(repo, proof_dir / "both")
    bound = boundary(repo, proof_dir / "boundary")
    anti = antithrash(repo, proof_dir / "anti")
    denom = denominator_control(repo, proof_dir / "denom")
    reviewer = reviewer_slip_attempts(repo, proof_dir / "reviewer")
    return {
        "both_states": both,
        "boundary": bound,
        "antithrash": anti,
        "denominator": denom,
        "reviewer": reviewer,
        "all_pass": all(
            x.get("pass") for x in (both, bound, anti, denom, reviewer)
        ),
    }
