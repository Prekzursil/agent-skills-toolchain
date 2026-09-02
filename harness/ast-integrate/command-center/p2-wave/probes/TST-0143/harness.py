#!/usr/bin/env python3
"""Live C03 evaluator for TST-0143.

Calls platform/lib/completion_predicate.py (the shared Gate-A reducer) and
reads condition 3 from the returned vector. File size is measured with an
independent Path.stat() on the same artifact; the intended write length is
never treated as proof.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "platform" / "lib"
SUT_REL = "platform/lib/completion_predicate.py"
SATISFIED = "SATISFIED"
UNSATISFIED = "UNSATISFIED"

# Declared floors exercised by the probes. Both sit above ABSOLUTE_MIN_BYTES=64
# so the declared floor is the binding constraint. 128 is the primary
# "legitimately small" floor; 80 is a second declared floor so a hardcoded-128
# checker cannot masquerade as using min_bytes_threshold.
FLOOR_PRIMARY = 128
FLOOR_ALT = 80
# Sub-absolute declared floor: live C03 must RAISE this to 64, not SATISFY at 40.
FLOOR_SUB_ABSOLUTE = 40


def load_reducer():
    sut = REPO / SUT_REL
    if not sut.is_file():
        raise FileNotFoundError(f"live completion predicate missing: {SUT_REL}")
    sys.path.insert(0, str(LIB))
    import completion_predicate as mod  # noqa: PLC0415

    if not hasattr(mod, "evaluate") or not hasattr(mod, "PredicateOptions"):
        raise ImportError(f"{SUT_REL} has no evaluate()/PredicateOptions")
    return sut, mod


def write_case(root: Path, name: str, size: int, floor: int) -> Path:
    """Materialize a workspace with a file of exactly `size` bytes."""
    ws = root / name
    ws.mkdir(parents=True, exist_ok=True)
    art = ws / "artifact.bin"
    art.write_bytes(b"A" * size)
    subject = {
        "artifact_rel": "artifact.bin",
        "min_bytes_threshold": floor,
        "state": "SUCCESS",
        "unit_id": "TST-0143",
    }
    (ws / "subject.json").write_text(
        json.dumps(subject, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ws


def independent_stat(path: Path) -> dict[str, Any]:
    st = path.stat()
    n_read = len(path.read_bytes())
    return {
        "path": str(path),
        "stat_st_size": int(st.st_size),
        "read_bytes_len": n_read,
        "is_file": path.is_file(),
    }


def _outcome_str(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def evaluate_c03(workspace: Path, reducer_mod) -> dict[str, Any]:
    art = workspace / "artifact.bin"
    stat = independent_stat(art)
    subject = json.loads((workspace / "subject.json").read_text(encoding="utf-8"))
    floor = int(subject["min_bytes_threshold"])
    receipt = {
        "unit_id": "TST-0143",
        "state": "SUCCESS",
        "min_bytes_threshold": floor,
        "artifacts": [{"path": "artifact.bin", "role": "primary"}],
    }
    opts = reducer_mod.PredicateOptions(repo_root=workspace)
    verdict = reducer_mod.evaluate(receipt, opts)
    row = verdict.condition(3)
    size = stat["stat_st_size"]
    absolute = int(getattr(reducer_mod, "ABSOLUTE_MIN_BYTES", 64))
    effective = max(floor, absolute)
    want = SATISFIED if size >= effective and size > 0 else UNSATISFIED
    detail = dict(row.detail or {})
    outcome = _outcome_str(row.outcome)
    return {
        "workspace": str(workspace),
        "floor": floor,
        "intended_size": size,
        "independent_stat": stat,
        "condition": row.to_dict(),
        "c03_outcome": outcome,
        "c03_basis": row.basis,
        "c03_detail": detail,
        "effective_min_bytes": detail.get("effective_min_bytes", effective),
        "absolute_min_bytes": absolute,
        "want_outcome": want,
        "vector_matches_stat": outcome == want,
        "stat_agrees_with_read": stat["stat_st_size"] == stat["read_bytes_len"],
        "reducer_overall": _outcome_str(verdict.verdict),
        "reducer_id": verdict.reducer_id,
    }


def nonempty_only_outcome(size: int) -> str:
    """Vacuous checker: any non-empty file passes. Must disagree at floor-1."""
    return SATISFIED if size > 0 else UNSATISFIED


def strict_exceeds_outcome(size: int, floor: int) -> str:
    """Checker that requires size > floor (rejects the exact floor)."""
    return SATISFIED if size > floor else UNSATISFIED
