#!/usr/bin/env python3
"""Probe 2: count-based cross-check against an independent scandir oracle.

Mechanically different from probe 1: this probe does not classify qualitative
outcomes. It only compares each component's reported item count with the
oracle. A silent skip produces a plausible result; only the count delta
exposes it. Rebuilds fixtures independently and does not read probe 1 output.
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
    UID,
    build_fixture_forest,
    mutant_casefold_hasher,
    oracle_list,
    platform_info,
    relpath_raises_on_reserved,
    run_component_isolated,
    swallowing_zero_walk,
    walk_files,
)

_ORIG = os.path.relpath


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def count_gate(oracle_n: int, reported_n: int, exception: str | None) -> dict:
    delta = int(reported_n) - int(oracle_n)
    silent_skip = exception is None and reported_n < oracle_n
    match = exception is None and reported_n == oracle_n
    return {
        "oracle_count": oracle_n,
        "reported_count": reported_n,
        "delta": delta,
        "match": match,
        "silent_skip": silent_skip,
        "exception": exception,
    }


def run_probe2() -> dict:
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="adv0117-p2-") as tmp_s:
        forest = build_fixture_forest(Path(tmp_s) / "forest")
        for class_id in ALL_CLASSES:
            spec = forest[class_id]
            root = Path(spec["root"])
            oracle_rels = oracle_list(root)
            oracle_n = len(oracle_rels)
            if oracle_n != spec["expected_count"]:
                # Oracle disagrees with the planter — protocol broken.
                rows.append(
                    {
                        "class_id": class_id,
                        "component": "oracle-self",
                        "oracle_rels": oracle_rels,
                        "gate": count_gate(spec["expected_count"], oracle_n, "oracle-mismatch"),
                    }
                )
            for component in COMPONENTS:
                raw = run_component_isolated(component, root, class_id)
                if component == "artifact-writer":
                    oracle_for_component = int(raw.get("attempted_count") or 0)
                else:
                    oracle_for_component = oracle_n
                gate = count_gate(
                    oracle_for_component,
                    int(raw.get("reported_count") or 0),
                    raw.get("exception"),
                )
                rows.append(
                    {
                        "class_id": class_id,
                        "component": component,
                        "source": raw.get("source"),
                        "oracle_rels": oracle_rels if component != "artifact-writer" else list(
                            raw.get("attempted") or []
                        ),
                        "reported_rels": list(raw.get("rels") or []),
                        "gate": gate,
                    }
                )

        ordinary_root = Path(forest["ordinary"]["root"])
        reserved_root = Path(forest["reserved-device"]["root"])
        case_root = Path(forest["case-collision"]["root"])

        ordinary_oracle = oracle_list(ordinary_root)
        ordinary_enum = walk_files(ordinary_root)
        ordinary_match = ordinary_enum.file_count == len(ordinary_oracle) and not ordinary_enum.aborted

        os.path.relpath = relpath_raises_on_reserved  # type: ignore[method-assign]
        try:
            swallowed = swallowing_zero_walk(reserved_root)
            production = walk_files(reserved_root)
        finally:
            os.path.relpath = _ORIG  # type: ignore[method-assign]

        reserved_oracle_n = len(oracle_list(reserved_root))
        swallowed_is_defect = swallowed["swallowed"] and swallowed["count"] == 0
        production_not_zero = production.file_count == reserved_oracle_n and not production.aborted
        crash_distinct = swallowed_is_defect and production_not_zero

        mutant_ordinary = mutant_casefold_hasher(ordinary_root)
        mutant_case = mutant_casefold_hasher(case_root)
        nc_casefold = {
            "id": "NC-CASEFOLD-HASHER-BOTH-STATES",
            "fired_on_bad_state": len(mutant_case) < len(oracle_list(case_root)),
            "silent_on_good_state": len(mutant_ordinary) == len(ordinary_oracle),
        }

        ordinary_rows = [
            r
            for r in rows
            if r["class_id"] == "ordinary" and r["component"] != "oracle-self"
        ]
        ordinary_all_match = all(r["gate"]["match"] for r in ordinary_rows)

        silent_skips = [
            r
            for r in rows
            if r["class_id"] != "ordinary" and r["gate"].get("silent_skip")
        ]

        protocol_ok = (
            ordinary_match
            and ordinary_all_match
            and crash_distinct
            and nc_casefold["fired_on_bad_state"]
            and nc_casefold["silent_on_good_state"]
            and forest["long-path"]["exceeds_max_path"]
        )

        payload = {
            "probe": "probe2-count-crosscheck",
            "unit_id": UID,
            "pass": protocol_ok,
            "computed_not_asserted": True,
            "independent": True,
            "reviewer_id": "ADV-0117-probe2-count-crosscheck",
            "starts_from": "fresh fixture forest + scandir oracle, not probe 1 matrix",
            "platform": platform_info(),
            "ordinary_control": {
                "oracle_count": len(ordinary_oracle),
                "enumerator_count": ordinary_enum.file_count,
                "all_components_match": ordinary_all_match,
                "match": ordinary_match,
            },
            "swallowed_exception_control": {
                "swallowed_count": swallowed["count"],
                "swallowed": swallowed["swallowed"],
                "swallowed_exception": swallowed["exception"],
                "production_count": production.file_count,
                "production_errors": list(production.errors),
                "crash_distinct_from_refusal": crash_distinct,
            },
            "negative_controls": [
                {
                    "id": "NC-SWALLOWED-ZERO-VS-PRODUCTION",
                    "fired_on_bad_state": swallowed_is_defect,
                    "silent_on_good_state": production_not_zero,
                    "note": (
                        "A swallowed ValueError on NUL becomes count=0. Production "
                        "walk_files still lists NUL, CON and keep.txt. That is a "
                        "distinct class from an explicit refusal."
                    ),
                },
                nc_casefold,
            ],
            "rows": rows,
            "silent_skips": [
                {
                    "class_id": r["class_id"],
                    "component": r["component"],
                    "delta": r["gate"]["delta"],
                    "oracle_count": r["gate"]["oracle_count"],
                    "reported_count": r["gate"]["reported_count"],
                }
                for r in silent_skips
            ],
        }
        return payload


def main() -> int:
    doc = run_probe2()
    print(json.dumps(doc, sort_keys=True, default=str))
    if doc.get("pass") is True:
        skips = len(doc.get("silent_skips") or [])
        print(
            f"SUCCESS:{UID}-probe2 count cross-check completed "
            f"ordinary_match={doc['ordinary_control']['match']} "
            f"silent_skips={skips}"
        )
        return 0
    return fail("count-gate protocol did not complete")


if __name__ == "__main__":
    raise SystemExit(main())
