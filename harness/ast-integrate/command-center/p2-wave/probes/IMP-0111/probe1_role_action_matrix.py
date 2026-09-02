#!/usr/bin/env python3
"""Named probe 1: every (role, action) cell, plus fail-closed unspecified."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.governance import (  # noqa: E402
    ACTIONS,
    ROLES,
    drop_policy_cell,
    evaluate,
    evaluate_full_matrix,
    load_policy,
)
from marketplace.registry import Registry  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = HERE / "probe1-matrix.raw.json"


def main() -> int:
    policy = load_policy()
    rows = evaluate_full_matrix(policy)
    expected = len(ROLES) * len(ACTIONS)
    if len(rows) != expected:
        print(f"FAILED:IMP-0111-probe1 matrix size {len(rows)} != {expected}")
        return 1
    unspecified = [r.as_dict() for r in rows if not r.specified]
    if unspecified:
        print("FAILED:IMP-0111-probe1 unspecified live cell")
        return 1
    mismatches = []
    for row in rows:
        cell = policy["matrix"][row.role][row.action]
        want_allow = cell["decision"] == "ALLOW"
        if bool(row.allowed) != want_allow:
            mismatches.append(row.as_dict())
    if mismatches:
        print("FAILED:IMP-0111-probe1 matrix mismatch")
        return 1

    stripped = drop_policy_cell(policy, "consumer", "promote")
    closed = evaluate("consumer", "promote", policy=stripped)
    if closed.allowed or not closed.fail_closed or closed.specified:
        print("FAILED:IMP-0111-probe1 unspecified cell did not fail closed")
        return 1
    unknown_role = evaluate("intruder", "publish", policy=policy)
    unknown_action = evaluate("owner", "explode", policy=policy)
    if unknown_role.allowed or unknown_action.allowed:
        print("FAILED:IMP-0111-probe1 unknown pair allowed")
        return 1

    registry = Registry(policy)
    denied = registry.perform(
        "anonymous",
        "publish",
        actor_id="anon",
        claimed_identity="anon",
        package_id="evil",
        version="0.0.1",
    )
    allowed = registry.perform(
        "owner",
        "publish",
        actor_id="owner",
        claimed_identity="owner",
        package_id="core",
        version="1.0.0",
    )
    if denied.performed or "evil@0.0.1" in registry.packages:
        print("FAILED:IMP-0111-probe1 denied publish mutated state")
        return 1
    if not allowed.performed or "core@1.0.0" not in registry.packages:
        print("FAILED:IMP-0111-probe1 allowed publish did not land")
        return 1

    payload = {
        "probe": "probe1-role-action-matrix",
        "unit_id": "IMP-0111",
        "cells": expected,
        "unspecified_live": 0,
        "matrix_mismatches": 0,
        "fail_closed_unspecified_cell": True,
        "fail_closed_unknown_role": (not unknown_role.allowed) and unknown_role.fail_closed,
        "fail_closed_unknown_action": (not unknown_action.allowed)
        and unknown_action.fail_closed,
        "denied_publish_performed": denied.performed,
        "allowed_publish_performed": allowed.performed,
        "rows": [r.as_dict() for r in rows],
        "pass": True,
    }
    RAW.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(
        "cells="
        + str(expected)
        + " unspecified_live=0"
        + " fail_closed_unspecified_cell=True"
        + " denied_performed="
        + str(denied.performed)
        + " allowed_performed="
        + str(allowed.performed)
    )
    print("SUCCESS:IMP-0111-probe1 role-action matrix and fail-closed unspecified cell")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
