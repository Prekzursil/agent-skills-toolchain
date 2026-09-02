#!/usr/bin/env python3
"""Probe 1: absent-tool candidate BLOCKED with the capability named (both-states).

Broken: typed requirement includes WebFetch, which the host cannot grant
→ status BLOCKED and missing_capabilities names WebFetch.

Twin: same shape with WebFetch replaced by a grantable tool
→ status IMPORTED, missing_capabilities empty.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from load_lib import ensure_import  # noqa: E402

ensure_import()
from workflow_foundry.tool_requirements import (  # noqa: E402
    extract_tool_requirements,
    import_candidate,
)

FIX = HERE / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0167-probe1 {msg}")
    return 1


def main() -> int:
    host = load("host_permissions.json")["grantable"]
    unit = load("unit_permissions.json")["tool_permissions"]
    absent = load("candidate_absent_webfetch.json")
    twin = load("candidate_grantable_twin.json")

    req_absent = extract_tool_requirements(absent)
    req_twin = extract_tool_requirements(twin)
    print(f"absent.required={sorted(req_absent)}")
    print(f"twin.required={sorted(req_twin)}")
    if "WebFetch" not in req_absent:
        return fail("absent candidate did not derive typed WebFetch")
    if "WebFetch" in req_twin:
        return fail("grantable twin still carries WebFetch")

    blocked = import_candidate(absent, unit_permissions=unit, host_grantable=host)
    imported = import_candidate(twin, unit_permissions=unit, host_grantable=host)
    print(
        json.dumps(
            {"blocked": blocked.as_dict(), "imported": imported.as_dict()},
            indent=2,
        )
    )

    if blocked.status != "BLOCKED":
        return fail(f"absent-tool imported silently status={blocked.status}")
    if "WebFetch" not in blocked.missing_capabilities:
        return fail(
            f"BLOCKED but capability not named: {blocked.missing_capabilities}"
        )
    if "WebFetch" not in blocked.missing_from_host:
        return fail(f"host-ungrantable not named: {blocked.missing_from_host}")
    if imported.status != "IMPORTED":
        return fail(
            f"grantable twin not imported: {imported.status} "
            f"missing={imported.missing_capabilities}"
        )
    if imported.missing_capabilities:
        return fail(f"grantable twin reported missing {imported.missing_capabilities}")
    if blocked.method != "set-subset" or imported.method != "set-subset":
        return fail("import did not record method=set-subset")

    print("both-states: BLOCKED names WebFetch; twin IMPORTED")
    print("SUCCESS:IMP-0167-probe1 absent-tool BLOCKED with capability named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
