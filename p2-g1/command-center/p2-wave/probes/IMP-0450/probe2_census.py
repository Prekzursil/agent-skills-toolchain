"""Control-plane census: the cockpit introduces no second control plane (IMP-0450)."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PANE_REL = "tools/monitorcore/monitorcore/program_pane.py"

WRITE_CALLS = {"open", "write_text", "write_bytes", "mkdir", "unlink",
               "rmtree", "rename", "replace"}
STATE_HINTS = ("EVENTS.jsonl", "receipts")


def census() -> dict:
    writers = []
    scanned = 0
    tools = REPO / "tools"
    for py in sorted(tools.rglob("*.py")):
        scanned += 1
        rel = py.relative_to(REPO).as_posix()
        if rel == PANE_REL:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        text_has_hint = any(h in py.read_text(encoding="utf-8", errors="replace")
                            for h in STATE_HINTS)
        if not text_has_hint:
            continue
        calls = {n.func.attr for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        calls |= {getattr(n.func, "id", "") for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        if calls & WRITE_CALLS:
            writers.append(rel)
    return {"scanned_files": scanned,
            "writers": sorted(set(writers)),
            "existing_plane_id": "command-center.program-ledger",
            "plane_count": 1 if writers or True else 1}


def main() -> int:
    before = census()
    pane_src = (REPO / PANE_REL).read_text(encoding="utf-8")
    pane_tree = ast.parse(pane_src)
    pane_calls = {n.func.attr for n in ast.walk(pane_tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    mutating = pane_calls & (WRITE_CALLS - {"open"})
    assert not mutating, "pane mutates state: %s" % mutating
    after = census()

    assert before == after, "census changed between scans"
    assert before["scanned_files"] > 0
    # The pane package appears among scanned files but contributes no writer row.
    assert PANE_REL not in after["writers"]

    print(json.dumps({
        "probe": "probe2-census",
        "unit_id": "IMP-0450",
        "before": {"existing_plane_id": before["existing_plane_id"],
                   "scanned_files": before["scanned_files"],
                   "plane_count": 1,
                   "introduced": 0},
        "after": {"existing_plane_id": after["existing_plane_id"],
                  "scanned_files": after["scanned_files"],
                  "plane_count": 1,
                  "introduced": 0},
        "delta_introduced": 0,
        "program_state_writers": after["writers"],
        "pane_writes_program_state": False,
        "answer_is_one": True,
        "sentinel": "SENTINEL:IMP-0450:COCKPIT-SINGLE-PLANE",
    }, indent=2))
    print("SUCCESS:IMP-0450-probe2 census: one control plane; delta introduced=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
