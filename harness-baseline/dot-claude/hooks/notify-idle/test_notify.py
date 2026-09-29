#!/usr/bin/env python3
r"""Tests for notify-idle/notify.py.

Run:  python test_notify.py          (no pytest required)
Also runnable with:  pytest test_notify.py -v

Proves:
  1. Valid payload → returns 0, balloon called, bell JSON printed to stdout.
  2. Bell JSON has correct shape: hookSpecificOutput.hookEventName="Notification",
     terminalSequence=BEL (\x07).
  3. Balloon receives title "Claude Code needs you" and the payload message as body.
  4. Empty message → graceful fallback body, still returns 0.
  5. NOTIFY_IDLE=off → returns 0, no balloon, no bell print.
  6. _send_balloon raises → main still returns 0 (fail-open).
  7. run() raises → main still returns 0 (fail-open, outer catch-all).
  8. Malformed / empty payload → returns 0, no crash.
"""

from __future__ import annotations

import io
import json
import os
import sys
import unittest.mock as mock
from contextlib import redirect_stdout
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

import notify  # noqa: E402 — the hook under test

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


def _run_and_capture(payload: dict, env_patch: dict | None = None) -> tuple[int, str]:
    """Call main(payload) while capturing stdout. Returns (return_code, stdout_str)."""
    buf = io.StringIO()
    patches: list = [mock.patch("notify._send_balloon")]
    if env_patch:
        patches.append(mock.patch.dict(os.environ, env_patch))

    with redirect_stdout(buf):
        ctx_stack = [p.__enter__() for p in patches]
        try:
            result = notify.main(payload)
        finally:
            for p, ctx in zip(reversed(patches), reversed(ctx_stack)):
                p.__exit__(None, None, None)

    return result, buf.getvalue().strip()


def _parse_bell_json(stdout: str) -> dict | None:
    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except Exception:
        return None


# ── test cases ────────────────────────────────────────────────────────────────


def test_normal_payload_returns_0_and_prints_bell():
    """Valid notification → returns 0, stdout contains bell JSON."""
    payload = {
        "session_id": "sess-abc",
        "cwd": "C:/proj",
        "message": "Waiting for your input",
        "hook_event_name": "Notification",
    }
    result, stdout = _run_and_capture(payload)
    ok("normal payload returns 0", result == 0, f"got {result}")
    ok("bell JSON printed to stdout", bool(stdout), f"stdout={stdout!r}")

    parsed = _parse_bell_json(stdout)
    ok("stdout is valid JSON", parsed is not None, f"stdout={stdout!r}")
    if parsed:
        hso = parsed.get("hookSpecificOutput", {})
        ok(
            "hookEventName=Notification",
            hso.get("hookEventName") == "Notification",
            f"hookEventName={hso.get('hookEventName')!r}",
        )
        ok(
            "terminalSequence is BEL (\\x07)",
            hso.get("terminalSequence") == "\x07",
            f"terminalSequence={hso.get('terminalSequence')!r}",
        )


def test_balloon_receives_correct_title_and_message():
    """Balloon is called with title 'Claude Code needs you' and the payload message as body."""
    payload = {
        "session_id": "s1",
        "message": "Permission required: write to /etc/hosts",
        "hook_event_name": "Notification",
    }
    buf = io.StringIO()
    with mock.patch("notify._send_balloon") as mock_balloon, redirect_stdout(buf):
        result = notify.main(payload)

    ok("balloon-title test returns 0", result == 0, f"got {result}")
    mock_balloon.assert_called_once()
    _args, kwargs = mock_balloon.call_args
    ok(
        "balloon title is 'Claude Code needs you'",
        kwargs.get("title") == "Claude Code needs you",
        f"title={kwargs.get('title')!r}",
    )
    ok(
        "balloon body contains the message",
        "Permission required" in kwargs.get("body", ""),
        f"body={kwargs.get('body', '')!r}",
    )


def test_empty_message_uses_fallback_body():
    """No message → fallback body, still returns 0, bell still emitted."""
    payload = {"session_id": "sess-xyz", "hook_event_name": "Notification"}
    buf = io.StringIO()
    with mock.patch("notify._send_balloon") as mock_balloon, redirect_stdout(buf):
        result = notify.main(payload)

    ok("empty-message returns 0", result == 0, f"got {result}")
    mock_balloon.assert_called_once()
    _args, kwargs = mock_balloon.call_args
    body = kwargs.get("body", "")
    ok("fallback body is non-empty", bool(body), f"body={body!r}")
    bell_json = _parse_bell_json(buf.getvalue().strip())
    ok("bell emitted on empty message", bell_json is not None, "no bell JSON")


def test_disabled_env_var_returns_0_no_balloon_no_bell():
    """NOTIFY_IDLE=off → returns 0, no balloon, no bell output."""
    payload = {
        "session_id": "s",
        "message": "test",
        "hook_event_name": "Notification",
    }
    result, stdout = _run_and_capture(payload, env_patch={"NOTIFY_IDLE": "off"})
    ok("disabled returns 0", result == 0, f"got {result}")
    ok("disabled: no stdout", stdout == "", f"stdout={stdout!r}")


def test_send_balloon_raises_still_returns_0():
    """_send_balloon raising must not propagate — main returns 0."""
    payload = {"session_id": "s", "message": "oops", "hook_event_name": "Notification"}
    buf = io.StringIO()
    with (
        mock.patch("notify._send_balloon", side_effect=OSError("no display")),
        redirect_stdout(buf),
    ):
        result = notify.main(payload)
    ok("balloon-raises returns 0", result == 0, f"got {result}")


def test_run_raises_main_still_returns_0():
    """If run() itself raises, the outer catch-all in main returns 0."""
    with (
        mock.patch.object(notify, "run", side_effect=RuntimeError("boom")),
        mock.patch("builtins.print"),
    ):
        result = notify.main({"session_id": "x", "message": "y"})
    ok("run-raises main returns 0", result == 0, f"got {result}")


def test_malformed_empty_payload_returns_0():
    """Empty / None-like values in payload → returns 0, no crash."""
    for payload in [{}, {"garbage": None}, {"message": None, "session_id": None}]:
        buf = io.StringIO()
        with mock.patch("notify._send_balloon"), redirect_stdout(buf):
            r = notify.main(payload)
        ok(f"malformed payload {payload!r} returns 0", r == 0, f"got {r}")


def test_ps_escape_helper_safety():
    """_escape_ps_dq correctly neutralises PowerShell metacharacters."""
    dangerous = '`$"hello`'
    result = notify._escape_ps_dq(dangerous)
    ok("backtick escaped", "``" in result, f"result={result!r}")
    ok("dollar sign escaped", "`$" in result, f"result={result!r}")
    ok("double-quote escaped", '`"' in result, f"result={result!r}")
    ok("length capped at 200", len(result) <= 200, f"len={len(result)}")


# ── runner ────────────────────────────────────────────────────────────────────


def main() -> int:
    tests = [
        test_normal_payload_returns_0_and_prints_bell,
        test_balloon_receives_correct_title_and_message,
        test_empty_message_uses_fallback_body,
        test_disabled_env_var_returns_0_no_balloon_no_bell,
        test_send_balloon_raises_still_returns_0,
        test_run_raises_main_still_returns_0,
        test_malformed_empty_payload_returns_0,
        test_ps_escape_helper_safety,
    ]
    for t in tests:
        try:
            t()
        except Exception as exc:
            import traceback

            _FAIL.append(t.__name__)
            print(f"FAIL: {t.__name__} [EXCEPTION] {exc}")
            traceback.print_exc()

    print(f"\n{'=' * 50}")
    print(f"RESULT: {len(_PASS)} passed, {len(_FAIL)} failed")
    if _FAIL:
        print("FAILED:", ", ".join(_FAIL))
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
