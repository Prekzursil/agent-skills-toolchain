#!/usr/bin/env python3
r"""test_todo_surfacer.py - unit test of the todo-surfacer inject predicate.

Imports hook.py and exercises build_message() directly (no subprocess): it must
return a message on the FIRE example and None on the SILENT example. The deeper
end-to-end proof (real stdin, exit codes, fail-open) is in chaos_todo_surfacer.py.
"""
from __future__ import annotations

import importlib.util
import atexit
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))
_TMP: list[str] = []

# Clean env: never disabled, state goes to a throwaway dir (cleaned at exit).
os.environ.pop("FORGE_TODO_SURFACER_OFF", None)
_STATE_ROOT = tempfile.mkdtemp(prefix="forge-state-test-")
_TMP.append(_STATE_ROOT)
os.environ["FORGE_STATE_ROOT"] = _STATE_ROOT


@atexit.register
def _cleanup_tmp() -> None:
    for p in _TMP:
        try:
            path = Path(p)
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()
        except Exception:
            pass


def _load_hook():
    spec = importlib.util.spec_from_file_location("forged_hook_todo_surfacer", HERE / "hook.py")
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
    p.setdefault("session_id", "unit")
    if kind == "response":
        tf = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        tf.write(json.dumps({"type": "assistant", "message": {"role": "assistant",
                 "content": [{"type": "text", "text": value}]}}) + "\n")
        tf.close()
        _TMP.append(tf.name)
        p["transcript_path"] = tf.name
    elif kind == "prompt":
        p["prompt"] = value
    elif kind == "command":
        p.setdefault("tool_input", {})["command"] = value
    elif kind == "tool":
        p["tool_name"] = value
    elif kind == "field":
        _set(p, FIX["field"], value)
    return p


def main() -> int:
    hook = _load_hook()
    msg = hook.build_message(_payload(FIX["fire_value"]))
    assert msg, "build_message returned nothing on the FIRE example"
    if FIX["has_silent"]:
        s = hook.build_message(_payload(FIX["silent_value"]))
        assert not s, f"build_message should be silent on the SILENT example, got: {s!r}"
        print(f"UNIT-PASS: {FIX['name']} fires on trigger ({msg!r}) and is silent otherwise")
    else:
        print(f"UNIT-PASS: {FIX['name']} fires on trigger ({msg!r})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"UNIT-FAIL: {exc}")
        sys.exit(1)
