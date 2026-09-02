#!/usr/bin/env python3
"""Probe 2: planted orphan fails the build; keyword lookalike does not (both-states)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import detector_ast, planted_both_states  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0174-probe2 {msg}")
    return 1


def main() -> int:
    both = planted_both_states()
    ast_rep = detector_ast()
    print(json.dumps({"both_states": both}, indent=2, sort_keys=True))
    print(json.dumps({"detector_ast": ast_rep}, indent=2, sort_keys=True))
    if not both["pass"]:
        return fail("planted orphan / lookalike both-states")
    if not ast_rep["pass"]:
        return fail("detector AST does not inspect provenance/source_span")
    if both["planted_id_contains_orphan"]:
        return fail("planted id contains 'orphan' (would fool a keyword detector)")
    if both["lookalike_orphan_count"] != 0:
        return fail("keyword lookalike treated as orphan")
    print(
        "good_silent planted_fires lookalike_silent "
        f"planted_id={both['planted_id']}"
    )
    print("SUCCESS:IMP-0174-probe2 planted orphan fails the build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
