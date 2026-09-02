#!/usr/bin/env python3
"""Production census for nested-council fan-in. Mechanically different from
the behavioural split probe: this is a filesystem + snippet check, not a
fan-in invocation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CANDIDATES = [
    "tools/council/topology/nested.py",
    "tools/council/simulate.py",
    "tools/council/fanin.py",
    "tools/council/__init__.py",
    "agentspec/oracle.py",
    "command-center/schema/confirmation-record.schema.json",
    "command-center/design/council/CNL-0037-nested-subcouncils-and-council-of-councils-fan-in.md",
    "command-center/design/council/CNL-0123-council-of-councils-fan-in-simulation-including-the-disagr.md",
    "command-center/confirmation/CNF-0095-council-of-councils-fanin.json",
]

FC11343_SNIPPET = "nested councils disagree on completion"
FAILURE_MODES = "command-center/phase3/A1/FAILURE-MODES.json"
# Production A1 dossier is absent on this worktree. Live spec text for
# FC-11343 lives in reconstructed prompt slices and the catalog unit itself.
SPEC_SOURCES = [
    FAILURE_MODES,
    "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md",
    "command-center/WORK-UNIT-CATALOG.json",
    "command-center/p2-wave/probes/SYN-0047/classes.py",
    "command-center/p2-wave/probes/CNL-0123/fanin.py",
]


def _exists(rel: str) -> dict[str, Any]:
    path = REPO / rel
    return {
        "path": rel,
        "present": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else 0,
    }


def census() -> dict[str, Any]:
    rows = [_exists(rel) for rel in CANDIDATES]
    council_dir = REPO / "tools" / "council"
    fm = REPO / FAILURE_MODES
    fc = None
    for rel in SPEC_SOURCES:
        path = REPO / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if FC11343_SNIPPET not in text:
            continue
        line = next(
            (
                i
                for i, row in enumerate(text.splitlines(), 1)
                if FC11343_SNIPPET in row
            ),
            None,
        )
        fc = {
            "path": rel,
            "present": True,
            "names_fc11343": True,
            "line": line,
            "production_failure_modes_present": fm.is_file(),
            "why_snippet": "Fan-in averaging; A1 has no nested council runtime.",
            "why_present": "Fan-in averaging; A1 has no nested council runtime." in text,
        }
        break
    if fc is None:
        fc = {
            "path": FAILURE_MODES if fm.is_file() else SPEC_SOURCES[1],
            "present": False,
            "names_fc11343": False,
            "line": None,
            "production_failure_modes_present": fm.is_file(),
            "why_snippet": "Fan-in averaging; A1 has no nested council runtime.",
            "why_present": False,
        }
    production_fanin = [r for r in rows if r["path"].startswith("tools/council") and r["present"]]
    return {
        "tools_council_dir": council_dir.is_dir(),
        "production_fanin_files": production_fanin,
        "production_nested_present": any(
            r["path"] == "tools/council/topology/nested.py" and r["present"] for r in rows
        ),
        "candidates": rows,
        "failure_modes_fc11343": fc,
        "object_under_test": "command-center/p2-wave/probes/CNF-0174/fanin.py",
        "object_under_test_reason": (
            "production nested runtime (tools/council/topology/nested.py) is "
            "absent; confirmer-authored completion-split fan-in is the object "
            "under test. CNL-0123 ships a sibling disagreement simulation with "
            "PASS/REFUTED labels, not COMPLETE/BLOCKED completion status."
        ),
    }
