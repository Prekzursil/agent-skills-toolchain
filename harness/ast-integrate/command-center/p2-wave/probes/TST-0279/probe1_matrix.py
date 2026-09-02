#!/usr/bin/env python3
"""Named probe 1: every typed role attempts every action; the matrix is the evidence.

Forbidden cells must be REFUSED. Permitted cells must be PERMITTED (no over-block).
A prompt-only role with no Mandate record is reported UNENFORCED, not greened.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from runtime import ACTIONS, TYPED_ROLES, expected_for, run_full_matrix  # noqa: E402


def main() -> int:
    result = run_full_matrix(enforce=True)
    n_roles = len(TYPED_ROLES)
    n_actions = len(ACTIONS)
    want_cells = n_roles * n_actions
    if result["cell_count"] != want_cells:
        print(
            f"FAILED:TST-0279-probe1 cell_count={result['cell_count']} want={want_cells}"
        )
        return 1
    if result["mismatches"]:
        print("FAILED:TST-0279-probe1 matrix mismatches")
        print(json.dumps(result["mismatches"][:8], indent=2)[:2000])
        return 1
    if result["forbidden_refused"] != result["forbidden_total"]:
        print(
            "FAILED:TST-0279-probe1 forbidden not fully refused "
            f"{result['forbidden_refused']}/{result['forbidden_total']}"
        )
        return 1
    if result["permitted_ok"] != result["permitted_total"]:
        print(
            "FAILED:TST-0279-probe1 over-block "
            f"{result['permitted_ok']}/{result['permitted_total']}"
        )
        return 1
    prompt_bad = [c for c in result["prompt_cells"] if not c["cell_ok"]]
    if prompt_bad:
        print("FAILED:TST-0279-probe1 prompt-only role was not UNENFORCED")
        print(json.dumps(prompt_bad[:4], indent=2)[:1000])
        return 1

    # Spot-check a few catalog-named cells so a swapped table still fails.
    spots = [
        ("observer", "vote", "REFUSED"),
        ("observer", "veto", "REFUSED"),
        ("guardian", "veto", "PERMITTED"),
        ("proposer", "judge", "REFUSED"),
        ("juror", "vote", "PERMITTED"),
        ("chair", "vote", "REFUSED"),
        ("synthesizer", "propose", "REFUSED"),
        ("judge", "read_source:hidden", "PERMITTED"),
        ("observer", "use_tool:exec", "REFUSED"),
        ("proposer", "use_tool:draft", "PERMITTED"),
    ]
    by = {(c["role"], c["action"]): c for c in result["cells"]}
    for role, action, want in spots:
        got = by[(role, action)]["observed"]
        if got != want or expected_for(role, action) != want:
            print(f"FAILED:TST-0279-probe1 spot {role} {action} got={got} want={want}")
            return 1

    summary = {
        "probe": "probe1_matrix",
        "typed_roles": n_roles,
        "actions": n_actions,
        "cells": want_cells,
        "forbidden_refused": f"{result['forbidden_refused']}/{result['forbidden_total']}",
        "permitted_ok": f"{result['permitted_ok']}/{result['permitted_total']}",
        "prompt_only_unenforced": all(c["cell_ok"] for c in result["prompt_cells"]),
        "matrix_ok": result["matrix_ok"],
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"matrix roles={n_roles} actions={n_actions} cells={want_cells} "
        f"forbidden_refused={result['forbidden_refused']}/{result['forbidden_total']} "
        f"permitted={result['permitted_ok']}/{result['permitted_total']}"
    )
    print("SUCCESS:TST-0279-probe1 role x forbidden-action matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
