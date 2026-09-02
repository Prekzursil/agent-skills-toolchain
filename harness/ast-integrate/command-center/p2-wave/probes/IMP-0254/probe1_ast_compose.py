#!/usr/bin/env python3
"""Probe 1: AST compose-only assertion + six-element contract both-states."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.library.ast_compose import check_mutant_fails, scan_entries  # noqa: E402
from tools.library.contract import (  # noqa: E402
    REQUIRED_ELEMENTS,
    ContractError,
    check_entry,
    mutate_omit,
    omission_codes,
)
from tools.library.entries import workflow_scout  # noqa: E402
from tools.library.load import load_library  # noqa: E402
from tools.library import registry  # noqa: E402


def _full_entry() -> dict:
    entry = dict(workflow_scout.ENTRY)
    entry["run"] = workflow_scout.run
    return entry


def main() -> int:
    rows = scan_entries()
    if len(rows) != 4:
        print(f"FAILED:IMP-0254-probe1 expected 4 entries, got {len(rows)}")
        return 1
    if not check_mutant_fails():
        print("FAILED:IMP-0254-probe1 planted ranking loop was accepted")
        return 1
    print("ast.entries_compose_only=True")
    print("ast.mutant_ranking_loop_rejected=True")

    base = _full_entry()
    present = check_entry(base)
    if set(present) != set(REQUIRED_ELEMENTS):
        print("FAILED:IMP-0254-probe1 complete entry did not report all six elements")
        return 1
    print("contract.complete_entry_accepted=True")

    codes = omission_codes()
    seen: list[str] = []
    for element in REQUIRED_ELEMENTS:
        mutant = mutate_omit(base, element)
        try:
            check_entry(mutant)
            print(f"FAILED:IMP-0254-probe1 omission of {element} was accepted")
            return 1
        except ContractError as exc:
            want = f"omit-{element}"
            if exc.code != want:
                print(f"FAILED:IMP-0254-probe1 want {want} got {exc.code}")
                return 1
            seen.append(exc.code)
            print(f"contract.omit[{element}].code={exc.code}")
    if seen != codes:
        print(f"FAILED:IMP-0254-probe1 omission codes {seen} != {codes}")
        return 1
    print("contract.six_distinct_omissions=True")

    ids = load_library()
    want = {
        "workflow-scout",
        "workflow-forge",
        "workflow-merger-composer",
        "workflow-tournament",
    }
    if set(ids) != want:
        print(f"FAILED:IMP-0254-probe1 registered {ids}")
        return 1
    for eid in ids:
        registry.smoke(eid)
        print(f"smoke[{eid}]=ok")
    print("SUCCESS:IMP-0254-probe1 ast-compose and six-element contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
