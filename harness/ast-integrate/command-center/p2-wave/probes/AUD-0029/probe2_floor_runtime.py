#!/usr/bin/env python3
"""Probe 2: import + unittest under the declared floor interpreter.

A passing run on the current interpreter proves nothing about the floor.
This probe launches CPython 3.10, 3.11, and 3.12 and checks both-states:
tomllib and 3.12 type-params fail on 3.10; at_floor and tools imports pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0029-probe2 {msg}")
    return 1


def main() -> int:
    matrix = E.runtime_matrix()
    falsify = matrix["falsify"]
    errors: list[str] = []
    if not falsify.get("pass"):
        for key, value in sorted(falsify.items()):
            if key == "pass":
                continue
            if value is not True:
                errors.append(f"{key}={value}")

    py310 = (matrix["runs"].get("3.10") or {}).get("compile_live") or {}
    py312 = (matrix["runs"].get("3.12") or {}).get("compile_live") or {}
    if py310.get("present") is False:
        errors.append("python 3.10 interpreter missing; floor runtime NOT-CHECKED")
    # Live tree should compile on 3.10 if the floor is API (tomllib) not syntax.
    # Do not require n_failed==0: any 3.11+ syntax is a finding, not a probe bug.
    if isinstance(py310.get("n_failed"), int) and isinstance(py312.get("n_failed"), int):
        if py312.get("n_failed") not in (0, None) and py312.get("n_failed") > 0:
            errors.append(f"current 3.12 failed to compile live files n_failed={py312.get('n_failed')}")

    node = matrix.get("node_runs") or {}
    if node.get("present"):
        at = node.get("at_floor") or {}
        if at.get("rc") != 0:
            errors.append(f"node at_floor rc={at.get('rc')} out={at.get('out')}")
        # newer-than-floor uses Promise.withResolvers; this host is Node 24 so it
        # SHOULD succeed here. That does not prove engines>=16. Recorded, not a fail.

    payload = {
        "probe": "probe2-floor-runtime",
        "unit_id": "AUD-0029",
        "interpreters": {
            mm: {
                "present": bool(
                    (matrix["interpreters"]["python"].get(mm) or {}).get("exe")
                    or (matrix["runs"].get(mm) or {}).get("present")
                ),
                "exe": (matrix["interpreters"]["python"].get(mm) or {}).get("exe"),
                "version": (matrix["interpreters"]["python"].get(mm) or {}).get("version"),
            }
            for mm in ("3.10", "3.11", "3.12")
        },
        "node": matrix["interpreters"].get("node"),
        "current": matrix["interpreters"].get("current"),
        "falsify": falsify,
        "compile_live": {
            mm: (matrix["runs"].get(mm) or {}).get("compile_live")
            for mm in ("3.10", "3.11", "3.12")
        },
        "import_tomllib": {
            mm: (matrix["runs"].get(mm) or {}).get("import_tomllib")
            for mm in ("3.10", "3.11", "3.12")
        },
        "onexc": {
            mm: {
                "run": (matrix["runs"].get(mm) or {}).get("fixture_onexc"),
                "signature": (matrix["runs"].get(mm) or {}).get("rmtree_accepts_onexc"),
            }
            for mm in ("3.10", "3.11", "3.12")
        },
        "tools_import_310": (matrix["runs"].get("3.10") or {}).get("import_tools"),
        "unittest_310": (matrix["runs"].get("3.10") or {}).get("unittest_at_floor"),
        "node_runs": {
            "present": node.get("present"),
            "version": node.get("version"),
            "at_floor_rc": (node.get("at_floor") or {}).get("rc"),
            "newer_rc": (node.get("newer") or {}).get("rc"),
            "current_only": node.get("current_only"),
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if errors:
        for item in errors:
            print(" ", item)
        return fail(f"{len(errors)} assertion(s)")
    print(
        "SUCCESS:AUD-0029-probe2 floor runtime: 3.10 rejects tomllib and 3.12 "
        "type-params; 3.11 imports tomllib; 3.12 accepts onexc; tools import on 3.10"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
