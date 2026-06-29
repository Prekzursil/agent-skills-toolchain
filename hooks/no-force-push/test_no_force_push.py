#!/usr/bin/env python3
r"""test_no_force_push.py - unit test of the no-force-push gate predicate.

Imports tripwire.py and exercises should_halt() directly: it must return
(True, reason) on the FIRE example and (False, _) on the SILENT example.
The end-to-end exit-2 / fail-open proof is in chaos_no_force_push.py.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))


def _load_tripwire():
    spec = importlib.util.spec_from_file_location("forged_tripwire_no_force_push", HERE / "tripwire.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _set(d: dict, path: str, val) -> None:
    parts = path.split(".")
    cur = d
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = val


def _payload(value: str) -> dict:
    kind = FIX["kind"]
    p = dict(FIX.get("extra_payload") or {})
    if kind == "prompt":
        p["prompt"] = value
    elif kind == "command":
        p.setdefault("tool_input", {})["command"] = value
    elif kind == "tool":
        p["tool_name"] = value
    elif kind == "field":
        _set(p, FIX["field"], value)
    return p


def main() -> int:
    tw = _load_tripwire()
    halt, reason = tw.should_halt(_payload(FIX["fire_value"]))
    assert halt, "should_halt did not fire on the FIRE example"
    assert reason, "should_halt fired but returned an empty reason"
    halt2, _ = tw.should_halt(_payload(FIX["silent_value"]))
    assert not halt2, "should_halt must NOT fire on the SILENT example"
    print(f"UNIT-PASS: {FIX['name']} halts on trigger ({reason!r}) and allows otherwise")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"UNIT-FAIL: {exc}")
        sys.exit(1)
