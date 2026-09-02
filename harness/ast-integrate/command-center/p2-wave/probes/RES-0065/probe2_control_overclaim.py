#!/usr/bin/env python3
"""Probe 2: control analogue absent + overclaim mutants go red."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    UNIT,
    assert_no_ci_platform_fields,
    check_claims,
    check_mapping,
    load_artifact,
    load_index,
    mutant_drop_rail,
    mutant_false_mapping,
    verify_local_captures,
)


def expect_fail(fn, label: str) -> str:
    try:
        fn()
    except AssertionError as exc:
        return f"{label}:RED:{exc}"
    raise AssertionError(f"{label} mutant stayed green")


def main() -> int:
    try:
        index = load_index()
        verify_local_captures(index)
        doc = load_artifact()
        scanned = assert_no_ci_platform_fields(doc)
        control = doc.get("control") or {}
        if control.get("blueprint_analogue") is not None:
            raise AssertionError("control claimed an analogue")
        refuted = [
            c
            for c in (doc.get("claims") or [])
            if c.get("verdict") == "REFUTED" and c.get("id") == "C-OVERCLAIM-JSON-IS-GHA-YAML"
        ]
        if not refuted:
            raise AssertionError("missing REFUTED JSON-is-GHA-YAML overclaim")

        drop = mutant_drop_rail(doc)
        red1 = expect_fail(lambda: check_claims(drop, index), "drop-rail")
        fmap = mutant_false_mapping(doc)
        red2 = expect_fail(lambda: check_mapping(fmap), "false-mapping")
    except (AssertionError, KeyError, json.JSONDecodeError, OSError) as exc:
        print(f"FAILED:{UNIT}-probe2 {exc}")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe2-control-overclaim",
                "unit_id": UNIT,
                "scanned_json": scanned,
                "control_analogue": control.get("blueprint_analogue"),
                "mutants": [red1, red2],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UNIT}-probe2 control-absent mutants-red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
