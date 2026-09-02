"""META-COMPOSITION cards P52-P58 expressed in the four primitives, or listed as gaps."""
from __future__ import annotations

from compose import compile_expr, PRIMITIVES

# Each tree uses only leaf + the four primitives. Nest supplies the
# diverge/converge bracket so a composer cannot put fan-in before fan-out
# without going through the compiler.

META_TREES = {
    "P52": {
        "slug": "nested-subcouncils-meta-council",
        "status": "EXPRESSIBLE",
        "gap_reason": None,
        "expr": {
            "op": "nest",
            "id": "P52-fan-out",
            "inners": [
                {"op": "leaf", "id": "child-council-A", "phase": "neutral"},
                {"op": "leaf", "id": "child-council-B", "phase": "neutral"},
            ],
        },
        "reading": (
            "nest = parallel child councils (diverge) then mandatory fan-in "
            "(converge). Sequence is not used for the split because sequence "
            "cannot express simultaneous children."
        ),
    },
    "P53": {
        "slug": "escalation-ladder",
        "status": "EXPRESSIBLE",
        "gap_reason": None,
        "expr": {
            "op": "repeat-until",
            "until": "resolved_or_top_rung",
            "body": {
                "op": "sequence",
                "steps": [
                    {"op": "leaf", "id": "current-rung-protocol", "phase": "neutral"},
                    {"op": "leaf", "id": "escalate-if-unresolved", "phase": "neutral"},
                ],
            },
        },
        "reading": (
            "Escalation is a sequence of rungs wrapped in repeat-until. It does "
            "not fan out, so nest is unused."
        ),
    },
    "P54": {
        "slug": "cross-vendor-mirrored",
        "status": "EXPRESSIBLE",
        "gap_reason": None,
        "expr": {
            "op": "nest",
            "id": "P54-mirror",
            "inners": [
                {"op": "leaf", "id": "vendor-A-copy", "phase": "neutral"},
                {"op": "leaf", "id": "vendor-B-copy", "phase": "neutral"},
            ],
        },
        "reading": "Two mirrored copies under nest: diverge, run, converge and compare.",
    },
    "P55": {
        "slug": "shadow-council",
        "status": "EXPRESSIBLE",
        "gap_reason": None,
        "expr": {
            "op": "nest",
            "id": "P55-shadow",
            "inners": [
                {"op": "leaf", "id": "primary-council", "phase": "neutral"},
                {"op": "leaf", "id": "shadow-council", "phase": "neutral"},
            ],
        },
        "reading": "Primary and silent shadow as nest inners; converge is the comparison point.",
    },
    "P56": {
        "slug": "minority-report-mandatory",
        "status": "EXPRESSIBLE",
        "gap_reason": None,
        "expr": {
            "op": "splice",
            "at": 1,
            "base": {
                "op": "sequence",
                "steps": [
                    {"op": "leaf", "id": "majority-protocol", "phase": "neutral"},
                    {"op": "leaf", "id": "majority-verdict", "phase": "neutral"},
                ],
            },
            "insert": {"op": "leaf", "id": "mandatory-minority-report", "phase": "neutral"},
        },
        "reading": (
            "Splice inserts the mandatory minority report into the majority "
            "sequence so it cannot be omitted by dropping a later optional step."
        ),
    },
    "P57": {
        "slug": "stopping-rule-tournament",
        "status": "EXPRESSIBLE",
        "gap_reason": None,
        "expr": {
            "op": "nest",
            "id": "P57-tournament",
            "inners": [
                {"op": "leaf", "id": "stop-rule-A", "phase": "neutral"},
                {"op": "leaf", "id": "stop-rule-B", "phase": "neutral"},
                {"op": "leaf", "id": "stop-rule-C", "phase": "neutral"},
            ],
        },
        "reading": "Competing stopping rules run as nest inners; converge picks the winner.",
    },
    "P58": {
        "slug": "owner-in-the-loop-stepwise",
        "status": "EXPRESSIBLE",
        "gap_reason": None,
        "expr": {
            "op": "repeat-until",
            "until": "owner_accepts",
            "body": {
                "op": "sequence",
                "steps": [
                    {"op": "leaf", "id": "work-step", "phase": "neutral"},
                    {"op": "leaf", "id": "owner-gate", "phase": "neutral"},
                ],
            },
        },
        "reading": (
            "Each increment is sequence(work, owner-gate) under repeat-until. "
            "The until predicate is a hole for CNL-0010's stopping grammar."
        ),
    },
}


def compile_all() -> dict:
    rows = []
    for pid in (f"P{n:02d}" for n in range(52, 59)):
        spec = META_TREES[pid]
        if spec["status"] == "GAP":
            rows.append(
                {
                    "id": pid,
                    "slug": spec["slug"],
                    "status": "GAP",
                    "gap_reason": spec["gap_reason"],
                    "accepted": None,
                    "used_ops": [],
                }
            )
            continue
        result = compile_expr(spec["expr"])
        used = sorted(
            {
                spec["expr"]["op"],
                *[
                    n.get("op")
                    for n in _walk(spec["expr"])
                    if n.get("op") in PRIMITIVES
                ],
            }
        )
        rows.append(
            {
                "id": pid,
                "slug": spec["slug"],
                "status": "EXPRESSIBLE" if result["accepted"] else "COMPILE-FAIL",
                "gap_reason": None if result["accepted"] else result.get("code"),
                "accepted": result["accepted"],
                "code": result.get("code"),
                "used_ops": used,
                "reading": spec["reading"],
            }
        )
    return {
        "primitives": list(PRIMITIVES),
        "rows": rows,
        "n": len(rows),
        "n_expressible": sum(1 for r in rows if r["status"] == "EXPRESSIBLE"),
        "n_gap": sum(1 for r in rows if r["status"] == "GAP"),
        "n_compile_fail": sum(1 for r in rows if r["status"] == "COMPILE-FAIL"),
        "all_expressible_or_gapped": all(
            r["status"] in {"EXPRESSIBLE", "GAP"} for r in rows
        ),
    }


def _walk(expr: dict):
    yield expr
    op = expr.get("op")
    if op == "sequence":
        for s in expr.get("steps") or []:
            yield from _walk(s)
    elif op == "nest":
        for s in expr.get("inners") or []:
            yield from _walk(s)
    elif op == "splice":
        yield from _walk(expr["base"])
        yield from _walk(expr["insert"])
    elif op == "repeat-until":
        yield from _walk(expr["body"])
