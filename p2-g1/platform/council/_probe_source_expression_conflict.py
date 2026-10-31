"""Probe: is `stopping.source_expression` compatible with the schema's own leaf annotations?

SEM-001 requires `parse(source_expression) == stopping.expression` EXACTLY. The expression
grammar's `unparse` emits only `<metric> <op> <value>`, so any OPTIONAL annotation the schema
allows on a leaf is invisible to the string form and cannot survive a round trip.

Two annotations are affected, and the schema offers both:
  * `producer` - stop_leaf_custom.properties.producer ("What computes this metric")
  * `note`     - present on ALL FOUR leaf branches (numeric, boolean, enum, custom)

So this is not a custom-metric corner case: a plain numeric leaf carrying a `note` is enough.

Run:  python platform/council/_probe_source_expression_conflict.py
"""

from __future__ import annotations

import copy
import json
import os
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "platform", "lib"))

from councilspec.expression import parse, unparse  # noqa: E402
from councilspec.semantics import check, errors  # noqa: E402

CUSTOM_TREE: Dict[str, Any] = {
    "all_of": [
        {"metric": "consensus", "op": ">=", "value": 0.8},
        {
            "metric": "custom:probe_flag",
            "op": "==",
            "value": True,
            "value_type": "boolean",
            "producer": "a clerk seat",
        },
    ]
}

NOTE_TREE: Dict[str, Any] = {
    "all_of": [
        {"metric": "consensus", "op": ">=", "value": 0.8},
        {
            "metric": "rounds_elapsed",
            "op": ">=",
            "value": 3,
            "note": "three rounds is the floor for this protocol",
        },
    ]
}


def _rules(spec: Dict[str, Any]) -> List[str]:
    return sorted({f.rule for f in errors(check(spec))})


def _warns(spec: Dict[str, Any]) -> List[str]:
    return sorted({f.rule for f in check(spec) if f.severity == "WARN"})


def _wrap(tree: Dict[str, Any], with_source: bool) -> Dict[str, Any]:
    spec = {"stopping": {"expression": copy.deepcopy(tree)}}
    if with_source:
        spec["stopping"]["source_expression"] = unparse(tree)
    return spec


def main() -> int:
    findings: List[Dict[str, Any]] = []
    failures: List[str] = []

    for label, tree, annotation in (
        ("custom-leaf producer", CUSTOM_TREE, "producer"),
        ("numeric-leaf note", NOTE_TREE, "note"),
    ):
        annotated = copy.deepcopy(tree)
        stripped = copy.deepcopy(tree)
        del stripped["all_of"][1][annotation]

        # State 1: annotation present AND source_expression present.
        s1 = _wrap(annotated, with_source=True)
        # State 2: annotation removed, source_expression present.
        s2 = _wrap(stripped, with_source=True)
        # State 3: annotation present, source_expression omitted.
        s3 = _wrap(annotated, with_source=False)

        row = {
            "annotation": annotation,
            "label": label,
            "unparse": unparse(annotated),
            "reparsed_equals_tree": parse(unparse(annotated)) == annotated,
            "state1_annotated_with_source": {
                "errors": _rules(s1),
                "warnings": _warns(s1),
            },
            "state2_stripped_with_source": {
                "errors": _rules(s2),
                "warnings": _warns(s2),
            },
            "state3_annotated_no_source": {
                "errors": _rules(s3),
                "warnings": _warns(s3),
            },
        }
        findings.append(row)

        # The claim under test, stated as three falsifiable assertions.
        if row["reparsed_equals_tree"]:
            failures.append(
                f"{label}: expected the round trip to LOSE the annotation, it did not"
            )
        if "SEM-001" not in row["state1_annotated_with_source"]["errors"]:
            failures.append(f"{label}: state 1 should raise SEM-001")
        if row["state3_annotated_no_source"]["errors"]:
            failures.append(f"{label}: state 3 should be clean")

    # DETECTOR CONTROL: a faithful source_expression on an UNANNOTATED tree must be clean, or
    # the probe is just observing a broken SEM-001 rather than a real incompatibility.
    control = _wrap(
        {
            "all_of": [
                {"metric": "consensus", "op": ">=", "value": 0.8},
                {"metric": "rounds_elapsed", "op": ">=", "value": 3},
            ]
        },
        with_source=True,
    )
    control_errors = _rules(control)
    if control_errors:
        failures.append(
            f"detector control failed: a faithful mirror errored {control_errors}"
        )

    out = {
        "claim": (
            "stopping.source_expression is mutually exclusive with any optional leaf annotation "
            "the schema permits (producer on custom leaves, note on every leaf), because unparse "
            "cannot express them and SEM-001 demands tree equality."
        ),
        "verdict": "CONFIRMED" if not failures else "REFUTED",
        "detector_control_faithful_mirror_errors": control_errors,
        "cases": findings,
        "failures": failures,
    }
    print(json.dumps(out, indent=2))
    if failures:
        print(
            f"FAILED:source-expression-conflict {len(failures)} assertion(s) did not hold"
        )
        return 1
    print(
        "SUCCESS:source-expression-conflict CONFIRMED for both `producer` and `note`; "
        "the only clean cell is annotation-present + source_expression-omitted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
