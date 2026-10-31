"""Measure the SEM-001 / SEM-012 incompatibility instead of asserting it.

Claim under test: for a stopping rule that uses a custom metric AND declares
`source_expression`, attaching the `producer` that SEM-012 asks for converts an advisory
warning into a hard SEM-001 error, so the two rules cannot both be satisfied.

Three states are measured in one run:
  A. as shipped                  -> expect 0 SEM-001 errors, N SEM-012 warnings
  B. producers attached          -> expect SEM-001 errors on every file that has a custom leaf
  C. producers + source dropped  -> expect 0 SEM-001 errors and 0 SEM-012 warnings

State C is the road not taken; measuring it proves the trade-off is real rather than assumed.
Nothing on disk is modified - every mutation is in memory.
"""

from __future__ import annotations

import copy
import os
import sys
from typing import Any, Dict

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LIB = os.path.join(_REPO, "platform", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from council_protocols._shared import PRODUCERS  # noqa: E402
from council_protocols.build import BUILDERS  # noqa: E402
from councilspec.validate import validate_spec  # noqa: E402


def attach(node: Any) -> int:
    """Attach the PRODUCERS entry to every custom leaf. Returns how many were touched."""
    if not isinstance(node, dict):
        return 0
    metric = node.get("metric")
    if isinstance(metric, str) and metric.startswith("custom:"):
        node["producer"] = PRODUCERS[metric]
        return 1
    n = 0
    for key in ("all_of", "any_of"):
        for child in node.get(key, []) or []:
            n += attach(child)
    if "not" in node:
        n += attach(node["not"])
    if "weighted" in node:
        for clause in node["weighted"].get("clauses", []) or []:
            n += attach(clause.get("when"))
    return n


def tally(label: str, mutate) -> Dict[str, int]:
    sem001 = sem012 = rejected = files_with_custom = attached = 0
    for builder in BUILDERS:
        spec = copy.deepcopy(builder())
        touched = mutate(spec)
        attached += touched
        if touched:
            files_with_custom += 1
        res = validate_spec(spec)
        if not res["ok"]:
            rejected += 1
        sem001 += sum(1 for m in res["semantic_errors"] if "SEM-001" in m)
        sem012 += sum(1 for m in res["warnings"] if "SEM-012" in m)
    print(
        f"{label:34} sem001_errors={sem001:3} sem012_warnings={sem012:3} "
        f"rejected={rejected:2}/12 files_with_custom_leaf={files_with_custom:2} "
        f"leaves_touched={attached:3}"
    )
    return {
        "sem001": sem001,
        "sem012": sem012,
        "rejected": rejected,
        "files_with_custom": files_with_custom,
    }


def state_a(spec) -> int:
    return 0


def state_b(spec) -> int:
    return attach(spec["stopping"]["expression"])


def state_c(spec) -> int:
    n = attach(spec["stopping"]["expression"])
    for stage in spec["protocol"]["sequence"]:
        if isinstance(stage.get("exit_when"), dict):
            n += attach(stage["exit_when"])
    spec["stopping"].pop("source_expression", None)
    return n


def main() -> int:
    a = tally("A as shipped", state_a)
    b = tally("B producers attached", state_b)
    c = tally("C producers + source dropped", state_c)

    checks = [
        ("A has zero SEM-001 errors", a["sem001"] == 0),
        ("A carries SEM-012 warnings (the cost)", a["sem012"] > 0),
        ("A is fully accepted", a["rejected"] == 0),
        (
            "B breaks SEM-001 on every custom-leaf file",
            b["sem001"] == b["files_with_custom"] > 0,
        ),
        (
            "B is rejected on exactly those files",
            b["rejected"] == b["files_with_custom"],
        ),
        ("C silences SEM-012 entirely", c["sem012"] == 0),
        ("C is accepted", c["rejected"] == 0),
    ]
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    bad = [n for n, ok in checks if not ok]
    print(
        "SUCCESS:proto3-sem001-vs-sem012 the two rules are mutually exclusive for a custom-metric "
        f"stopping rule with a source_expression ({b['sem001']} SEM-001 errors when producers are "
        f"attached vs {a['sem012']} SEM-012 warnings when they are not)"
        if not bad
        else f"FAILED:proto3-sem001-vs-sem012 {bad}"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
