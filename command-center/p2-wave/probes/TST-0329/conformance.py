"""TST-0329: single-condition conformance battery for the CC-0003 shared reducer.

Builds a healthy receipt (TRUE), applies twelve single-condition mutations (each
FALSE), and verifies independence by evaluating all twelve conditions on every
mutant. Condition 2 is the spec-line-10646 case: exit_code=0 with a missing
artifact.

Reuses the CC-0003 Case fixture + mutators from
platform/lib/test_completion_predicate.py so the battery stays bound to the
shared reducer rather than inventing a parallel oracle.
"""

from __future__ import annotations

import importlib.util
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[4]
PLATFORM_LIB = REPO / "platform" / "lib"
sys.path.insert(0, str(PLATFORM_LIB))

from completion_predicate import (  # noqa: E402
    CONDITIONS,
    CONDITION_TEXT,
    Outcome,
    Verdict,
    evaluate,
)


def _load_cc0003_tests():
    path = PLATFORM_LIB / "test_completion_predicate.py"
    spec = importlib.util.spec_from_file_location("cc0003_tcp", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cc0003_tcp"] = mod
    spec.loader.exec_module(mod)
    return mod


_TCP = _load_cc0003_tests()
Case = _TCP.Case
EXPECTED_CASCADE: dict[int, list[int]] = dict(_TCP.EXPECTED_CASCADE)
BASE_MUTATORS: dict[int, Callable] = dict(_TCP.MUTATORS)


def _m2_exit0_missing_artifact(c: Any) -> tuple[dict, dict]:
    """C2 / :10646: exit_code zero with a missing artifact is still FALSE.

    Keeps a SUCCESS terminal state so condition 1 stays green; plants exit_code=0
    as the tempting false signal; deletes the primary artifact so only condition 2
    is UNSATISFIED (3/4/5 become NOT-CHECKED via the documented cascade).
    """
    r = deepcopy(c.receipt)
    r["exit_code"] = 0
    # Downstream consumers also report exit 0 — must not greenwash a missing artifact.
    for consumer in r.get("downstream_consumers") or []:
        if isinstance(consumer, dict):
            consumer["exit_code"] = 0
            consumer["executed"] = True
            consumer["read_ok"] = True
    (c.root / c.artifact_rel).unlink()
    return r, {}


MUTATORS: dict[int, Callable] = dict(BASE_MUTATORS)
MUTATORS[2] = _m2_exit0_missing_artifact

MUTATION_DESCRIPTIONS: dict[int, str] = {
    1: "state=TIMEOUT (non-success terminal); sentinel family left coherent",
    2: (
        "exit_code=0 with primary artifact deleted on disk "
        "(spec :10646 — exit code zero alone is never success)"
    ),
    3: "min_bytes_threshold raised above on-disk artifact size",
    4: "required schema field 'verdict' dropped from artifact bytes",
    5: "artifact sentinel field replaced with non-matching string",
    6: "source and verifier probes share one fingerprint (same-probe-rerun)",
    7: "required test result rewritten from PASS to SKIP",
    8: "negative control fired_on_bad_state forced False (inert detector)",
    9: "reviewer.vendor set equal to produced_by.vendor (same-vendor)",
    10: "open P1 defect appended to defects[]",
    11: "ARTIFACT-MANIFEST.json rewritten to empty artifacts list",
    12: "downstream_consumers[0].read_ok=False with exit_code=1",
}


def run_healthy(root: Path) -> dict[str, Any]:
    c = Case(root / "healthy")
    result = evaluate(c.receipt, c.options())
    return {
        "is_complete": bool(result.is_complete),
        "verdict": result.verdict.value,
        "unsatisfied": list(result.unsatisfied),
        "not_checked": list(result.not_checked),
        "satisfied_count": result.counts["satisfied"],
        "per_condition": [
            {
                "n": cond.n,
                "text": cond.text,
                "outcome": cond.outcome.value,
                "basis": cond.basis,
            }
            for cond in result.conditions
        ],
        "sentinel_line": result.sentinel_line,
        "exit_code_field": c.receipt.get("exit_code"),
    }


def run_mutation(root: Path, n: int) -> dict[str, Any]:
    c = Case(root / f"m{n:02d}")
    receipt, over = MUTATORS[n](c)
    result = evaluate(receipt, c.options(**over))
    per = [
        {
            "n": cond.n,
            "text": cond.text,
            "outcome": cond.outcome.value,
            "basis": cond.basis,
        }
        for cond in result.conditions
    ]
    unsat = list(result.unsatisfied)
    not_checked = list(result.not_checked)
    independent = unsat == [n] and not_checked == EXPECTED_CASCADE.get(n, [])
    return {
        "condition": n,
        "condition_text": CONDITION_TEXT[n],
        "mutation": MUTATION_DESCRIPTIONS[n],
        "is_complete": bool(result.is_complete),
        "verdict": result.verdict.value,
        "reducer_verdict": (
            "FALSE"
            if not result.is_complete
            else "TRUE"
        ),
        "unsatisfied": unsat,
        "not_checked": not_checked,
        "expected_cascade_not_checked": EXPECTED_CASCADE.get(n, []),
        "independent": independent,
        "per_condition": per,
        "sentinel_line": result.sentinel_line,
        "exit_code_zero_present": receipt.get("exit_code") == 0
        or any(
            isinstance(x, dict) and x.get("exit_code") == 0
            for x in (receipt.get("downstream_consumers") or [])
        ),
        "is_10646_case": n == 2,
    }


def run_battery(root: Path) -> dict[str, Any]:
    healthy = run_healthy(root)
    rows = [run_mutation(root, n) for n in range(1, 13)]
    all_false = all(r["reducer_verdict"] == "FALSE" and not r["is_complete"] for r in rows)
    all_independent = all(r["independent"] for r in rows)
    case_10646 = next(r for r in rows if r["is_10646_case"])
    ok = (
        healthy["is_complete"] is True
        and healthy["verdict"] == Verdict.COMPLETE.value
        and all_false
        and all_independent
        and case_10646["exit_code_zero_present"] is True
        and case_10646["unsatisfied"] == [2]
    )
    return {
        "unit": "TST-0329",
        "reducer": "platform/lib/completion_predicate.py",
        "dep_cc0003": "command-center/receipts/CC-0003.json",
        "conditions": [{"n": n, "text": t, "spec_line": line} for n, t, line in CONDITIONS],
        "healthy": healthy,
        "rows": rows,
        "row_count": len(rows),
        "all_twelve_false": all_false,
        "all_independent": all_independent,
        "case_10646_covered": case_10646["is_10646_case"]
        and case_10646["exit_code_zero_present"]
        and case_10646["reducer_verdict"] == "FALSE",
        "ok": ok,
        "both_states": {
            "healthy_true": healthy["is_complete"] is True,
            "mutations_all_false": all_false,
        },
    }


def table_markdown(report: dict[str, Any]) -> str:
    lines = [
        "| # | condition | mutation | reducer_verdict | unsatisfied | independent |",
        "|---|-----------|----------|-----------------|-------------|-------------|",
    ]
    for row in report["rows"]:
        lines.append(
            f"| {row['condition']} | {row['condition_text']} | "
            f"{row['mutation']} | {row['reducer_verdict']} | "
            f"{row['unsatisfied']} | {row['independent']} |"
        )
    return "\n".join(lines) + "\n"


__all__ = [
    "MUTATORS",
    "MUTATION_DESCRIPTIONS",
    "Case",
    "EXPECTED_CASCADE",
    "run_battery",
    "run_healthy",
    "run_mutation",
    "table_markdown",
]
