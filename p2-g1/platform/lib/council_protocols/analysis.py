"""Exact both-states + leaf-necessity analysis for CouncilSpec stopping expressions.

Why brute force rather than "set every leaf to a satisfying value": polarity. A leaf under a
``not`` node, or inside a ``weighted`` clause, satisfies the ROOT when its own comparison is
FALSE. A generator that assumes leaf-true => root-true silently produces a "satisfying"
snapshot that does not satisfy the rule, and then reports the failure as a defect in the
protocol. With <= ~8 leaves the full 2**n polarity enumeration is cheap and cannot be wrong
about which side of the gate a snapshot lands on.

Outputs per expression tree:

* ``satisfying``      - a metric snapshot for which ``evaluate`` returns True
* ``not_satisfying``  - a metric snapshot for which ``evaluate`` returns False
* ``load_bearing``    - how many single-leaf flips off ``satisfying`` turn the rule False
* ``survivors``       - the leaves whose single flip does NOT change the verdict

For an ``all_of`` root every leaf must be load-bearing; a survivor there is decoration
masquerading as a condition. For ``any_of`` / ``weighted`` roots survivors are the intended
semantics, so the requirement is only that both states exist.
"""

from __future__ import annotations

import itertools
import os
import sys
from typing import Any, Dict, List, Mapping, Tuple

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from councilspec.expression import evaluate, iter_leaves  # noqa: E402
from councilspec.registry import CUSTOM_PREFIX, domain_of  # noqa: E402

_OTHER_ENUM = {"PASS": "FAIL", "CONFIRMED": "REFUTED", "DECIDED": "NO_DECISION"}


def _step(value: float | int) -> float | int:
    if isinstance(value, int):
        return 1
    return max(0.05, round(abs(value) * 0.25, 6)) or 0.05


def leaf_values(leaf: Mapping[str, Any]) -> Tuple[Any, Any]:
    """Return (value_making_comparison_true, value_making_comparison_false)."""
    metric, op, want = leaf["metric"], leaf["op"], leaf["value"]
    domain = "custom" if metric.startswith(CUSTOM_PREFIX) else domain_of(metric)
    declared = leaf.get("value_type") if domain == "custom" else None

    if domain == "boolean" or declared == "boolean":
        return (want, not want) if op == "==" else (not want, want)

    if domain == "enum" or declared == "string":
        other = _OTHER_ENUM.get(want, "FAIL" if want != "FAIL" else "PASS")
        return (want, other) if op == "==" else (other, want)

    d = _step(want)
    table = {
        ">=": (want, want - d),
        ">": (want + d, want),
        "<=": (want, want + d),
        "<": (want - d, want),
        "==": (want, want + d),
        "!=": (want + d, want),
    }
    return table[op]


def analyse(tree: Mapping[str, Any]) -> Dict[str, Any]:
    leaves = list(iter_leaves(tree))
    metrics = [lf["metric"] for lf in leaves]
    duplicate = sorted({m for m in metrics if metrics.count(m) > 1})
    values = [leaf_values(lf) for lf in leaves]

    def snapshot(bits: Tuple[int, ...]) -> Dict[str, Any]:
        return {metrics[i]: values[i][0 if bits[i] else 1] for i in range(len(leaves))}

    n = len(leaves)
    all_true = tuple([1] * n)
    # Prefer the all-comparisons-true assignment; fall back to any assignment that satisfies.
    order = [all_true] + [
        b for b in itertools.product((1, 0), repeat=n) if b != all_true
    ]
    sat_bits = next((b for b in order if evaluate(tree, snapshot(b))), None)
    unsat_bits = next((b for b in order if not evaluate(tree, snapshot(b))), None)

    result: Dict[str, Any] = {
        "root": next(
            k for k in ("all_of", "any_of", "not", "weighted", "metric") if k in tree
        ),
        "leaves": n,
        "duplicate_metrics": duplicate,
        "satisfiable": sat_bits is not None,
        "falsifiable": unsat_bits is not None,
        "satisfying": snapshot(sat_bits) if sat_bits else None,
        "not_satisfying": snapshot(unsat_bits) if unsat_bits else None,
        "load_bearing": 0,
        "survivors": [],
    }
    if result["root"] == "metric":
        result["root"] = "leaf"
    if sat_bits is None:
        return result

    survivors: List[str] = []
    caught = 0
    for i in range(n):
        flipped = list(sat_bits)
        flipped[i] = 0 if flipped[i] else 1
        if evaluate(tree, snapshot(tuple(flipped))):
            survivors.append(metrics[i])
        else:
            caught += 1
    result["load_bearing"] = caught
    result["survivors"] = survivors
    return result


def all_trees(spec: Mapping[str, Any]):
    """Yield (path, tree) for the stopping rule and every stage exit condition."""
    top = (spec.get("stopping") or {}).get("expression")
    if isinstance(top, Mapping):
        yield "stopping.expression", top
    for stage in (spec.get("protocol") or {}).get("sequence") or []:
        if isinstance(stage, Mapping) and isinstance(stage.get("exit_when"), Mapping):
            yield (
                f"protocol.sequence[{stage.get('stage_id', '?')}].exit_when",
                stage["exit_when"],
            )
