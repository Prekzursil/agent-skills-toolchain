#!/usr/bin/env python3
"""Probe 1: rights matrix — each right exercised with and without the grant."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.roles.mandate import (  # noqa: E402
    MODULE_REL,
    RIGHTS,
    empty_mandate,
    mandate_granting,
    point_of_use_audit,
    seat,
    speak,
    use_tool,
    rights_matrix,
)

UNIT = "IMP-0280"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    src = REPO / MODULE_REL
    if not src.is_file():
        return fail(f"{MODULE_REL} missing")

    cells = rights_matrix()
    if len(cells) != len(RIGHTS):
        return fail(f"matrix width {len(cells)} want {len(RIGHTS)}")
    failed = [c["right"] for c in cells if not c["pass"]]
    if failed:
        return fail(f"cells not discriminating: {failed}")

    # Independence: speaking grant must not leak a vote grant.
    speaker = seat("s-speak", mandate_granting("critic", "speaking", "note"))
    if not speak(speaker, "I mention a vote").allowed:
        return fail("granted speaking was refused")
    from council.roles.mandate import cast_vote  # noqa: E402

    leaked = cast_vote(speaker, "aye")
    if leaked.allowed:
        return fail("speaking grant leaked a vote")

    # A tool grant is name-exact: 'search' does not imply 'exec'.
    searcher = seat("s-tool", mandate_granting("analyst", "tool_access", "search"))
    if not use_tool(searcher, "search").allowed:
        return fail("granted tool was refused")
    if use_tool(searcher, "exec").allowed:
        return fail("ungranted sibling tool was allowed")

    denied = seat("s-empty", empty_mandate("empty"))
    if use_tool(denied, "search").allowed:
        return fail("empty mandate allowed a tool")

    audit = point_of_use_audit()
    if audit.unenforced_rights():
        return fail(f"live audit unenforced={list(audit.unenforced_rights())}")
    if set(audit.enforced_rights()) != set(RIGHTS):
        return fail(f"live audit enforced={list(audit.enforced_rights())}")

    payload = {
        "probe": "probe1-rights-matrix",
        "unit_id": UNIT,
        "rights": list(RIGHTS),
        "cells": cells,
        "independence": {
            "speaking_does_not_grant_vote": not leaked.allowed,
            "tool_grant_is_name_exact": True,
        },
        "audit_enforced": list(audit.enforced_rights()),
        "audit_unenforced": list(audit.unenforced_rights()),
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    granted = sum(1 for c in cells if c["with_grant"]["allowed"])
    refused = sum(1 for c in cells if not c["without_grant"]["allowed"])
    print(f"rights={len(RIGHTS)} granted_ok={granted} refused_ok={refused}")
    print("SUCCESS:IMP-0280-probe1 rights matrix with/without grant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
