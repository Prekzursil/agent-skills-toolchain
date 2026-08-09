"""Differential between the TWO gate-A reducers this wave produced, on identical inputs.

Measured 2026-08-09: `platform/lib/` now holds two independent implementations of gate A --

  * platform/lib/completion_predicate.py :: evaluate()          (unit contracts/completion-predicate)
  * platform/lib/receipt_schema_gate.py         :: evaluate_gate_a()   (the receipt-envelope lane)

plus the pre-existing partial one at hooks/_shared/completion.py. That is the seeded failure class
"two completion predicates disagree" (_USER-PROMPTS.md:11314) being manufactured inside the wave that
was told to build ONE. This probe does not editorialise: it runs both reducers over the identical
baseline case and the identical twelve isolated mutations and reports, per input, whether the two
agree on COMPLETE/not-COMPLETE and on WHICH condition blocks.

An orchestrator picking one implementation needs the disagreement set, not the headcount.

Exit 0 when the comparison completed with a passing control (both reducers must accept the baseline;
if either rejects it, the comparison is meaningless and says so). A non-zero exit means the
comparison could not be made - never that one reducer is "wrong".
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from completion_predicate import evaluate  # noqa: E402
from test_completion_predicate import MUTATORS, Case  # noqa: E402


def _twin_available() -> tuple[Any, str | None]:
    try:
        import receipt_schema_gate  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001 - the sibling lane may be mid-write
        return None, f"receipt_schema_gate not importable: {exc}"
    if not hasattr(receipt_schema_gate, "evaluate_gate_a"):
        return None, "receipt_schema_gate has no evaluate_gate_a"
    return receipt_schema_gate, None


def _twin_view(twin: Any, receipt: dict[str, Any], root: Path) -> dict[str, Any]:
    try:
        res = twin.evaluate_gate_a(receipt, repo_root=root)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}
    blocking = [c.n for c in res.conditions if c.blocking]
    unsat = [c.n for c in res.conditions if c.outcome == "UNSATISFIED"]
    return {
        "complete": bool(res.complete),
        "blocking": blocking,
        "unsatisfied": unsat,
        "schema_errors": len(res.schema_errors),
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ns = ap.parse_args()

    twin, why = _twin_available()
    rows: list[dict[str, Any]] = []
    control: dict[str, Any] = {}

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        if twin is not None:
            c = Case(base / "control")
            mine = evaluate(c.receipt, c.options())
            theirs = _twin_view(twin, c.receipt, c.root)
            control = {
                "mine_complete": mine.is_complete,
                "theirs_complete": theirs.get("complete"),
                "theirs_detail": theirs,
                "both_accept_baseline": bool(
                    mine.is_complete and theirs.get("complete")
                ),
            }
            for n in sorted(MUTATORS):
                cc = Case(base / f"m{n}")
                receipt, over = MUTATORS[n](cc)
                m = evaluate(receipt, cc.options(**over))
                t = _twin_view(twin, receipt, cc.root)
                rows.append(
                    {
                        "condition": n,
                        "mine_complete": m.is_complete,
                        "mine_unsatisfied": m.unsatisfied,
                        "mine_not_checked": m.not_checked,
                        "theirs_complete": t.get("complete"),
                        "theirs_unsatisfied": t.get("unsatisfied"),
                        "theirs_blocking": t.get("blocking"),
                        "theirs_error": t.get("error"),
                        "agree_on_completeness": (m.is_complete == t.get("complete")),
                        "agree_on_blamed_condition": (
                            t.get("unsatisfied") is not None
                            and sorted(m.unsatisfied) == sorted(t["unsatisfied"])
                        ),
                    }
                )

    disagree_completeness = [
        r["condition"] for r in rows if not r["agree_on_completeness"]
    ]
    disagree_blame = [
        r["condition"] for r in rows if not r["agree_on_blamed_condition"]
    ]
    report = {
        "artifact": "platform/lib/_predicate_twin_differential.py output",
        "reducers_compared": [
            "platform/lib/completion_predicate.py::evaluate",
            "platform/lib/receipt_schema_gate.py::evaluate_gate_a",
        ],
        "third_partial_implementation": "hooks/_shared/completion.py (conditions 2 and 5 only)",
        "twin_unavailable_reason": why,
        "control": control,
        "rows": rows,
        "disagree_on_completeness": disagree_completeness,
        "disagree_on_blamed_condition": disagree_blame,
    }
    blob = json.dumps(report, indent=2)
    if ns.out:
        Path(ns.out).write_text(blob + "\n", encoding="utf-8")
    else:
        print(blob)

    if twin is None:
        print(f"FAILED:predicate-twin-differential could not compare: {why}")
        return 1
    if not control.get("both_accept_baseline"):
        print(
            "FAILED:predicate-twin-differential control did not pass - one reducer rejects the "
            "baseline, so any disagreement count below would be meaningless"
        )
        return 1
    print(
        "SUCCESS:predicate-twin-differential two gate-A reducers compared over 12 mutations: "
        f"completeness_disagreements={disagree_completeness} "
        f"blamed_condition_disagreements={disagree_blame}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
