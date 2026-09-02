#!/usr/bin/env python3
"""Probe 2: independent named-strictness + garbage + empty-receipt controls.

Does not import probe1 results. Reloads the schema from disk and mutates the
positive fixture itself.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from schema_validate import (  # noqa: E402
    GARBAGE,
    SCHEMA_REL,
    as_blocked,
    error_messages,
    is_valid,
    load_fixture,
    load_schema,
)


def drop_valid(base: dict, key: str) -> bool:
    d = copy.deepcopy(base)
    d.pop(key, None)
    return is_valid(d)


def main() -> int:
    schema = load_schema()
    pos = load_fixture("positive.json")
    if not is_valid(pos, schema):
        print(json.dumps({"pass": False, "reason": "positive-invalid"}))
        print("FAILED:IMP-0433-probe2 positive fixture INVALID")
        return 1

    named = {
        label: (not drop_valid(pos, key))
        for label, key in (
            ("sentinel", "sentinel"),
            ("evidence", "evidence"),
            ("reviewer", "reviewer"),
        )
    }
    blocked = as_blocked(pos)
    blocked_named = {
        label: (not drop_valid(blocked, key))
        for label, key in (
            ("sentinel", "sentinel"),
            ("evidence", "evidence"),
            ("reviewer", "reviewer"),
        )
    }
    garbage_rejected = []
    for i, g in enumerate(GARBAGE):
        errs = error_messages(g, schema)
        garbage_rejected.append({"i": i, "rejected": bool(errs), "n_errors": len(errs)})

    empty_rejected = not is_valid({}, schema)
    want_named = named == {"sentinel": True, "evidence": True, "reviewer": True}
    want_blocked = (
        blocked_named["sentinel"] is True
        and blocked_named["evidence"] is True
        and blocked_named["reviewer"] is False
    )
    want_garbage = all(r["rejected"] for r in garbage_rejected)

    payload = {
        "pass": want_named and want_blocked and want_garbage and empty_rejected,
        "probe": "probe2-named-strictness",
        "schema": SCHEMA_REL,
        "named_strictness_success": named,
        "named_strictness_blocked": blocked_named,
        "garbage_rejected": garbage_rejected,
        "empty_receipt_rejected": empty_rejected,
    }
    print(json.dumps(payload, sort_keys=True))
    if not want_named:
        print("FAILED:IMP-0433-probe2 SUCCESS named strictness", named)
        return 1
    if not want_blocked:
        print("FAILED:IMP-0433-probe2 BLOCKED named strictness", blocked_named)
        return 1
    if not want_garbage or not empty_rejected:
        print("FAILED:IMP-0433-probe2 garbage/empty not rejected")
        return 1
    print("SUCCESS:IMP-0433-probe2 named strictness + garbage controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
