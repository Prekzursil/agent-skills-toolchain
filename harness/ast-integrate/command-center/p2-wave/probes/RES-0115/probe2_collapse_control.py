#!/usr/bin/env python3
"""Probe 2: collapse-to-one control + treat-as-real overclaim guard."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import independence as I  # noqa: E402
import schema_local as SL  # noqa: E402

ART = REPO / "command-center/research/RES-0115.json"
SCHEMA = REPO / "command-center/schema/research-registry.schema.json"
SENTINEL = (
    "SUCCESS:RES-0115 in the receipt AND a failure register with an "
    "independent-reporter count and at least one documented collapse to one"
)
FIXTURES = [
    HERE / "fixtures/hn-search-collapse.json",
    HERE / "fixtures/shared-primitive.json",
    HERE / "fixtures/quote-collapse.json",
    HERE / "fixtures/independent-pair.json",
]
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000},
)


def run_fixture(path: Path) -> None:
    fx = json.loads(path.read_text(encoding="utf-8"))
    got = I.collapse_reporters(fx["reporters"])
    exp = fx["expect"]
    for key in ("raw_reporter_count", "independent_reporter_count", "verdict"):
        if got[key] != exp[key]:
            raise SystemExit(
                f"FAILED:RES-0115-probe2 fixture {fx.get('id')} {key} "
                f"got={got[key]!r} expect={exp[key]!r}"
            )
    print(
        f"fixture[{fx.get('id')}] raw={got['raw_reporter_count']} "
        f"independent={got['independent_reporter_count']} "
        f"verdict={got['verdict']}"
    )


def main() -> int:
    for path in FIXTURES:
        run_fixture(path)

    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        print("FAILED:RES-0115-probe2 declared schema missing")
        return 1
    validator = SL.validator()
    rejected = 0
    for g in GARBAGE:
        errs = list(validator.iter_errors(g))
        if errs:
            rejected += 1
    if rejected != 3:
        print(f"FAILED:RES-0115-probe2 schema garbage rejected {rejected}/3")
        return 1

    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    errs = list(validator.iter_errors(doc))
    if errs:
        print("FAILED:RES-0115-probe2 schema-invalid")
        for e in errs[:8]:
            print(" ", list(e.path), e.message)
        return 1
    if SENTINEL not in text:
        print("FAILED:RES-0115-probe2 sentinel absent")
        return 1
    view = SL.artifact_view(doc)
    register = view.get("failure_register") or view.get("register") or []
    controls = [
        r
        for r in register
        if isinstance(r, dict)
        and r.get("collapse_control") is True
        and (r.get("independence_check") or {}).get("verdict") == "collapsed-to-one"
        and int(r.get("independent_reporter_count") or 0) == 1
        and int(r.get("raw_reporter_count") or 0) > 1
    ]
    if not controls:
        print("FAILED:RES-0115-probe2 no documented collapse-to-one control")
        return 1
    print(f"collapse_control_rows={[c.get('id') for c in controls]}")

    for r in register:
        if not isinstance(r, dict):
            continue
        treated = r.get("treated_as_real") is True
        expected = I.treat_as_real(
            int(r.get("independent_reporter_count") or 0),
            bool(r.get("vendor_doc_present")),
            bool(r.get("vendor_tracker_present")),
            2,
        )
        if treated != expected:
            print(
                f"FAILED:RES-0115-probe2 treat_as_real mismatch {r.get('id')} "
                f"artifact={treated} expected={expected}"
            )
            return 1
        if treated and (
            r.get("vendor_doc_present") or r.get("vendor_tracker_present")
        ):
            print(
                f"FAILED:RES-0115-probe2 overclaim {r.get('id')} treated_as_real "
                "despite vendor presence"
            )
            return 1

    refuted = [
        c
        for c in (view.get("claims") or [])
        if isinstance(c, dict) and c.get("id") == "C-posttooluse-mcp"
    ]
    if not refuted or refuted[0].get("verdict") != "REFUTED":
        print("FAILED:RES-0115-probe2 missing REFUTED PostToolUse-MCP overclaim")
        return 1
    print("schema_garbage_rejected=3/3 overclaim_guard=ok")
    print("SUCCESS:RES-0115-probe2 collapse-to-one control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
