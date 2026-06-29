#!/usr/bin/env python3
r"""Tests for session-end/end.py.

Run:  python test_end.py          (no pytest required)
Also runnable with:  pytest test_end.py -v

Proves:
  1. Valid payload → returns 0, ledger.append called once.
  2. Unflushed spools present → ledger.append called a second time with unflushed_count.
  3. SESSION_END=off → returns 0, ledger not touched.
  4. Ledger raises → main still returns 0 (fail-open).
  5. run() raises → main still returns 0 (fail-open, outer catch-all).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest.mock as mock
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

import end  # noqa: E402 — the hook under test

# ── helpers ───────────────────────────────────────────────────────────────────

_PASS: list[str] = []
_FAIL: list[str] = []


def ok(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"PASS: {name}")
        _PASS.append(name)
    else:
        print(f"FAIL: {name}" + (f" — {detail}" if detail else ""))
        _FAIL.append(name)


def _make_spool_file(title: str = "my-note") -> Path:
    """Write a fake spool JSON to a temp file and return its Path."""
    tf = tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", delete=False, encoding="utf-8"
    )
    tf.write(json.dumps({"title": title, "ts": 9_999_999.0, "key": "aabbcc112233"}))
    tf.close()
    return Path(tf.name)


def _mock_ledger():
    """Return a fresh MagicMock ledger with append returning a sentinel dict."""
    ml = mock.MagicMock()
    ml.append.return_value = {"seq": 1, "kind": "note"}
    return ml


# ── test cases ────────────────────────────────────────────────────────────────

def test_normal_payload_returns_0():
    """Valid SessionEnd payload: returns 0, ledger.append called at least once."""
    payload = {
        "session_id": "sess-abc-123456",
        "cwd": "C:/some/project",
        "reason": "clear",
        "hook_event_name": "SessionEnd",
    }
    ml = _mock_ledger()
    with mock.patch.object(end, "_ledger", ml), \
         mock.patch.object(end, "_list_spools", return_value=[]):
        result = end.main(payload)

    ok("normal payload returns 0", result == 0, f"got {result}")
    ok("ledger.append called once", ml.append.call_count == 1,
       f"call_count={ml.append.call_count}")
    # Check shape of the call
    _args, kwargs = ml.append.call_args_list[0]
    ok("append has reason kwarg", kwargs.get("reason") == "clear",
       f"reason={kwargs.get('reason')!r}")
    ok("append has hook=session-end", kwargs.get("hook") == "session-end",
       f"hook={kwargs.get('hook')!r}")
    ok("append has session kwarg", "session" in kwargs,
       f"kwargs keys: {list(kwargs)}")


def test_unflushed_spools_triggers_second_append():
    """When unflushed spools exist, ledger.append is called a second time with unflushed_count."""
    sp = _make_spool_file("important-note")
    try:
        payload = {
            "session_id": "sess-xyz",
            "cwd": "C:/proj",
            "reason": "logout",
            "hook_event_name": "SessionEnd",
        }
        ml = _mock_ledger()
        with mock.patch.object(end, "_ledger", ml), \
             mock.patch.object(end, "_list_spools", return_value=[sp]):
            result = end.main(payload)

        ok("unflushed-spool path returns 0", result == 0, f"got {result}")
        ok("append called twice (checkpoint + spool-note)",
           ml.append.call_count == 2, f"call_count={ml.append.call_count}")
        _args, kwargs2 = ml.append.call_args_list[1]
        ok("second append has unflushed_count=1",
           kwargs2.get("unflushed_count") == 1,
           f"unflushed_count={kwargs2.get('unflushed_count')!r}")
        ok("second append text mentions unflushed",
           "unconfirmed" in kwargs2.get("text", "").lower() or
           "unflushed" in kwargs2.get("text", "").lower(),
           f"text={kwargs2.get('text', '')[:80]!r}")
    finally:
        sp.unlink(missing_ok=True)


def test_disabled_env_var_returns_0_no_ledger():
    """SESSION_END=off → returns 0, ledger untouched."""
    payload = {"session_id": "s", "cwd": "C:/", "reason": "clear"}
    ml = _mock_ledger()
    with mock.patch.object(end, "_ledger", ml), \
         mock.patch.object(end, "_list_spools", return_value=[]), \
         mock.patch.dict(os.environ, {"SESSION_END": "off"}):
        result = end.main(payload)

    ok("disabled returns 0", result == 0, f"got {result}")
    ok("disabled: no ledger calls", ml.append.call_count == 0,
       f"call_count={ml.append.call_count}")


def test_ledger_append_raises_still_returns_0():
    """Even if ledger.append raises, main returns 0 (fail-open)."""
    payload = {"session_id": "s", "cwd": "C:/", "reason": "other"}
    ml = _mock_ledger()
    ml.append.side_effect = RuntimeError("disk full")
    with mock.patch.object(end, "_ledger", ml), \
         mock.patch.object(end, "_list_spools", return_value=[]):
        result = end.main(payload)

    ok("ledger-raises still returns 0", result == 0, f"got {result}")


def test_run_raises_main_still_returns_0():
    """If run() itself raises, the outer catch-all in main returns 0."""
    with mock.patch.object(end, "run", side_effect=RuntimeError("boom")):
        result = end.main({"session_id": "x"})
    ok("run-raises main still returns 0", result == 0, f"got {result}")


def test_malformed_empty_payload_returns_0():
    """Empty / None-like payload: returns 0, doesn't crash."""
    ml = _mock_ledger()
    with mock.patch.object(end, "_ledger", ml), \
         mock.patch.object(end, "_list_spools", return_value=[]):
        r1 = end.main({})
        r2 = end.main({"garbage_key": None})
    ok("empty payload returns 0", r1 == 0, f"got {r1}")
    ok("garbage payload returns 0", r2 == 0, f"got {r2}")


def test_no_ledger_module_returns_0():
    """If _ledger is None (import failed), run returns 0 gracefully."""
    with mock.patch.object(end, "_ledger", None):
        result = end.main({"session_id": "s", "cwd": "C:/", "reason": "clear"})
    ok("no-ledger-module returns 0", result == 0, f"got {result}")


# ── runner ────────────────────────────────────────────────────────────────────

def main() -> int:
    tests = [
        test_normal_payload_returns_0,
        test_unflushed_spools_triggers_second_append,
        test_disabled_env_var_returns_0_no_ledger,
        test_ledger_append_raises_still_returns_0,
        test_run_raises_main_still_returns_0,
        test_malformed_empty_payload_returns_0,
        test_no_ledger_module_returns_0,
    ]
    for t in tests:
        try:
            t()
        except Exception as exc:
            import traceback
            _FAIL.append(t.__name__)
            print(f"FAIL: {t.__name__} [EXCEPTION] {exc}")
            traceback.print_exc()

    print(f"\n{'='*50}")
    print(f"RESULT: {len(_PASS)} passed, {len(_FAIL)} failed")
    if _FAIL:
        print("FAILED:", ", ".join(_FAIL))
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
