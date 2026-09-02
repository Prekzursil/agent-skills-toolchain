#!/usr/bin/env python3
"""Probe 1: both-states control.

SEPARABLE mechanisms (retry, HITL, fan-out, barrier, resume) execute on an A1
JSON workflow with no foreign runtime import.

NON-SEPARABLE worker-poll / scheduler stages raise NonSeparable and must not
be sketched.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return p
    raise SystemExit("FAILED:probe1 repo root not found")


REPO = repo_root(HERE)
sys.path.insert(0, str(HERE))

from mechanisms import MECHANISMS  # noqa: E402
from sketch import (  # noqa: E402
    FOREIGN_RUNTIMES,
    NON_SEPARABLE_DEMO,
    SEPARABLE_DEMO,
    NonSeparable,
    execute,
)

ART = REPO / "command-center/wfa/WFA-0027-teardown-adjacent-runtimes.json"


def _imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def main() -> int:
    if not ART.is_file():
        print("FAILED:WFA-0027-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0027" not in json.dumps(doc):
        print("FAILED:WFA-0027-probe1 sentinel absent")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0027-probe1 self-declared", doc.get("state"))
        return 1

    paused = execute(SEPARABLE_DEMO, {})
    good_pause = paused.get("status") == "awaiting_human" and "finish" not in (
        paused.get("payload") or {}
    )
    resumed = execute(SEPARABLE_DEMO, {**paused, "human": "approve"})
    payload = resumed.get("payload") or {}
    good_resume = (
        resumed.get("status") == "done"
        and payload.get("join") == ["a", "b", "c"]
        and (payload.get("flaky") or {}).get("attempts") == 3
        and payload.get("approve") == "approve"
        and payload.get("finish") == "closed"
    )

    nonsep_fired = False
    try:
        execute(NON_SEPARABLE_DEMO, {})
    except NonSeparable:
        nonsep_fired = True

    unit_py = [
        HERE / "sketch.py",
        HERE / "mechanisms.py",
        HERE / "emit_report.py",
        HERE / "probe1_both_states.py",
        HERE / "probe2_overclaim.py",
    ]
    leaked = []
    for path in unit_py:
        leaked.extend(sorted(set(_imports_of(path)) & set(FOREIGN_RUNTIMES)))
    no_import = not leaked

    rejected = [m for m in MECHANISMS if m["verdict"] == "NON-SEPARABLE"]
    sketched_rejected = [m for m in rejected if m.get("a1_sketch") is not None]
    sep = [m for m in MECHANISMS if m["verdict"] == "SEPARABLE"]
    unsketched_sep = [m for m in sep if m.get("a1_sketch") is None]

    print(
        json.dumps(
            {
                "good_pause": good_pause,
                "good_resume": good_resume,
                "non_separable_refused": nonsep_fired,
                "no_foreign_import": no_import,
                "rejected_unsketched": not sketched_rejected,
                "separable_sketched": not unsketched_sep,
            }
        )
    )
    if not (
        good_pause
        and good_resume
        and nonsep_fired
        and no_import
        and not sketched_rejected
        and not unsketched_sep
    ):
        print("FAILED:WFA-0027-probe1 both-states did not discriminate")
        if leaked:
            print("leaked", leaked)
        if sketched_rejected:
            print("sketched_rejected", [m["runtime"] + "/" + m["mechanism"] for m in sketched_rejected])
        return 1
    print("SUCCESS:WFA-0027-probe1 both-states separable runs, non-separable refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
