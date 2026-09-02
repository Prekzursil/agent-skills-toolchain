#!/usr/bin/env python3
"""Probe 1: run each path-handling component over every hostile-class fixture.

Per-class outcome is one of: correct, crash, silent skip, wrong result,
explicit refusal, swallowed_zero. The ordinary-path fixture is the green
control. A naive os.path.relpath walker under a reserved-name monkeypatch
is the red control. Findings are recorded; they are not a probe failure.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from probe_common import (  # noqa: E402
    ALL_CLASSES,
    COMPONENTS,
    HOSTILE_CLASSES,
    UID,
    build_fixture_forest,
    classify_outcome,
    mutant_casefold_hasher,
    naive_relpath_walk,
    oracle_list,
    outcome_to_verdict,
    platform_info,
    relpath_raises_on_reserved,
    run_component_isolated,
    swallowing_zero_walk,
    walk_files,
)

_ORIG = os.path.relpath


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def score_row(class_id: str, spec: dict, component: str, raw: dict) -> dict:
    expected_rels = list(spec["expected_rels"])
    expected_count = int(spec["expected_count"])
    if component == "artifact-writer":
        expected_count = int(raw.get("attempted_count") or 2)
        expected_rels = list(raw.get("attempted") or [])
        expected_sha = None
        reported_sha = None
    else:
        expected_sha = spec.get("expected_sha256")
        reported_sha = raw.get("sha256")
    outcome = classify_outcome(
        expected_count=expected_count,
        reported_count=int(raw.get("reported_count") or 0),
        expected_rels=expected_rels if component != "artifact-writer" else None,
        reported_rels=list(raw.get("rels") or []) if component != "artifact-writer" else None,
        expected_sha=expected_sha if component == "manifest-hasher" else None,
        reported_sha=reported_sha if component == "manifest-hasher" else None,
        exception=raw.get("exception"),
        aborted=bool(raw.get("aborted")),
        errors=list(raw.get("errors") or []),
        explicit_refusal=False,
        swallowed_zero=bool(raw.get("aborted"))
        and int(raw.get("reported_count") or 0) == 0
        and not raw.get("errors")
        and not raw.get("exception"),
    )
    if (
        component == "artifact-writer"
        and outcome == "correct"
        and raw.get("extra_parseable") is False
        and int(raw.get("reported_count") or 0) > 0
    ):
        outcome = "wrong_result"
    return {
        "class_id": class_id,
        "component": component,
        "outcome": outcome,
        "verdict": outcome_to_verdict(outcome),
        "expected_count": expected_count,
        "reported_count": int(raw.get("reported_count") or 0),
        "expected_rels": expected_rels,
        "reported_rels": list(raw.get("rels") or []),
        "errors": list(raw.get("errors") or []),
        "exception": raw.get("exception"),
        "aborted": bool(raw.get("aborted")),
        "source": raw.get("source"),
        "hasher_disagreement": raw.get("hasher_disagreement"),
        "extra_parseable": raw.get("extra_parseable"),
        "longest_rel": spec.get("longest_rel"),
        "exceeds_max_path": spec.get("exceeds_max_path"),
    }


def run_probe1() -> dict:
    matrix: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="adv0117-p1-") as tmp_s:
        base = Path(tmp_s)
        forest = build_fixture_forest(base / "forest")

        # Production components over each class (fresh tree, no writer pollution).
        for class_id in ALL_CLASSES:
            spec = forest[class_id]
            root = Path(spec["root"])
            for component in COMPONENTS:
                raw = run_component_isolated(component, root, class_id)
                matrix.append(score_row(class_id, spec, component, raw))

        ordinary = forest["ordinary"]
        reserved = forest["reserved-device"]

        # Control: ordinary enumerator vs oracle.
        ordinary_oracle = oracle_list(Path(ordinary["root"]))
        ordinary_enum = walk_files(Path(ordinary["root"]))
        ordinary_match = sorted(posix_rel for posix_rel in ordinary_oracle) == sorted(
            f.rel.replace("\\", "/") for f in ordinary_enum.files
        ) and ordinary_enum.file_count == len(ordinary_oracle)

        # Red control: naive relpath under reserved-name monkeypatch.
        os.path.relpath = relpath_raises_on_reserved  # type: ignore[method-assign]
        try:
            naive_exc = None
            naive_count = None
            try:
                naive_files = naive_relpath_walk(Path(reserved["root"]))
                naive_count = len(naive_files)
            except (OSError, ValueError) as exc:
                naive_exc = f"{type(exc).__name__}:{exc}"
                naive_count = 0
            production_under_patch = walk_files(Path(reserved["root"]))
            swallowed = swallowing_zero_walk(Path(reserved["root"]))
        finally:
            os.path.relpath = _ORIG  # type: ignore[method-assign]

        naive_went_red = naive_exc is not None or naive_count == 0
        production_green = (
            not production_under_patch.aborted
            and production_under_patch.file_count == reserved["expected_count"]
            and {f.name for f in production_under_patch.files} >= {"NUL", "CON", "keep.txt"}
        )
        swallowed_is_zero = bool(swallowed["swallowed"]) and swallowed["count"] == 0
        crash_distinct = (
            naive_went_red
            and swallowed_is_zero
            and production_green
            and bool(production_under_patch.file_count)
        )

        # Casefold hasher mutant: detector must go red on case-collision, stay silent on ordinary.
        mutant_ordinary = mutant_casefold_hasher(Path(ordinary["root"]))
        mutant_case = mutant_casefold_hasher(Path(forest["case-collision"]["root"]))
        nc_casefold = {
            "id": "NC-CASEFOLD-HASHER-BOTH-STATES",
            "fired_on_bad_state": len(mutant_case)
            < forest["case-collision"]["expected_count"],
            "silent_on_good_state": len(mutant_ordinary) == ordinary["expected_count"],
            "ordinary_count": len(mutant_ordinary),
            "case_collision_count": len(mutant_case),
        }

        long_spec = forest["long-path"]
        long_ok = bool(long_spec["exceeds_max_path"])

        protocol_ok = (
            ordinary_match
            and naive_went_red
            and crash_distinct
            and nc_casefold["fired_on_bad_state"]
            and nc_casefold["silent_on_good_state"]
            and long_ok
            and not ordinary_enum.aborted
        )

        payload = {
            "probe": "probe1-component-matrix",
            "unit_id": UID,
            "pass": protocol_ok,
            "computed_not_asserted": True,
            "platform": platform_info(),
            "classes": {
                cid: {
                    "expected_count": forest[cid]["expected_count"],
                    "expected_rels": forest[cid]["expected_rels"],
                    "longest_rel": forest[cid]["longest_rel"],
                    "exceeds_max_path": forest[cid]["exceeds_max_path"],
                    "notes": forest[cid]["notes"],
                }
                for cid in ALL_CLASSES
            },
            "matrix": matrix,
            "ordinary_control": {
                "oracle_count": len(ordinary_oracle),
                "enumerator_count": ordinary_enum.file_count,
                "match": ordinary_match,
                "oracle_rels": ordinary_oracle,
            },
            "reserved_relpath_control": {
                "naive_went_red": naive_went_red,
                "naive_exception": naive_exc,
                "naive_count": naive_count,
                "production_green": production_green,
                "production_count": production_under_patch.file_count,
                "production_names": sorted({f.name for f in production_under_patch.files}),
                "production_errors": list(production_under_patch.errors),
                "swallowed_zero": swallowed,
                "crash_distinct_from_refusal": crash_distinct,
            },
            "negative_controls": [
                {
                    "id": "NC-NAIVE-RELPATH-RESERVED",
                    "fired_on_bad_state": naive_went_red,
                    "silent_on_good_state": ordinary_match,
                    "note": (
                        "Unguarded os.path.relpath raises ValueError on NUL/CON "
                        "(catalog precedent). Production walk_files stays green."
                    ),
                },
                nc_casefold,
            ],
            "hostile_classes": list(HOSTILE_CLASSES),
            "components": list(COMPONENTS),
        }
        return payload


def main() -> int:
    doc = run_probe1()
    print(json.dumps(doc, sort_keys=True, default=str))
    if doc.get("pass") is True:
        n = len(doc.get("matrix") or [])
        print(
            f"SUCCESS:{UID}-probe1 component matrix completed "
            f"rows={n} ordinary_match="
            f"{doc['ordinary_control']['match']} naive_red="
            f"{doc['reserved_relpath_control']['naive_went_red']}"
        )
        return 0
    return fail("protocol did not complete (ordinary/naive/long-path/casefold control)")


if __name__ == "__main__":
    raise SystemExit(main())
