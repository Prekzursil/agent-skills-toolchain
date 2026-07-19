#!/usr/bin/env python
"""Self-contained tests for the anti-degeneration fingerprint hook.

Run: python test_fingerprint.py

Uses ANTI_DEGEN_ROOT pointed at a temp dir so real session files are untouched.

Tests:
  1. 3× identical (same args + same output) → warning injected (the stuck-loop case)
  2. 3× same args but DIFFERENT output → NO warning (polling-tool false-positive guard)
  3. 4× identical after already warned → still warns (no state reset needed)
  4. Two different sessions are isolated (no cross-contamination)
  5. Missing/malformed stdin → exit 0, no output (fail-open)
  6. Non-dict tool_input is hashed consistently (no crash)
"""

from __future__ import annotations

import importlib
import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
fails: list[str] = []


def check(name: str, cond: bool) -> None:
    symbol = "OK " if cond else "BAD"
    print(f"  {symbol}  {name}")
    if not cond:
        fails.append(name)


def _make_stdin(session_id: str, tool_name: str, tool_input, tool_response: str) -> str:
    return json.dumps(
        {
            "session_id": session_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_response": tool_response,
            "cwd": "C:/fake/project",
        }
    )


def _run_hook(mod, stdin_str: str) -> tuple[int, str]:
    """Run mod.main() with stdin replaced; return (exit_code, captured_stdout)."""
    old_stdin, old_stdout = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(stdin_str)
    cap = io.StringIO()
    sys.stdout = cap
    try:
        rc = mod.main()
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout
    return rc, cap.getvalue()


def _load_fresh(tmp_dir: str):
    """Load a fresh (re-imported) copy of fingerprint.py against tmp_dir."""
    os.environ["ANTI_DEGEN_ROOT"] = tmp_dir
    spec = importlib.util.spec_from_file_location(
        "fingerprint_under_test", HERE / "fingerprint.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # patch the module-level ROOT to the temp dir (it reads the env at import time)
    mod.ROOT = Path(tmp_dir)
    return mod


def _has_warning(stdout: str) -> bool:
    """Return True if stdout contains the anti-degen additionalContext JSON."""
    for line in stdout.strip().splitlines():
        try:
            payload = json.loads(line)
            ctx = payload.get("hookSpecificOutput", {}).get("additionalContext", "")
            if "repeated" in ctx and "identical" in ctx:
                return True
        except Exception:
            continue
    return False


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="anti-degen-test-")

    # ── Test 1: 3× identical (same args + same output) → warning ──────────────
    print("== Test 1: 3× identical calls trigger warning ==")
    mod = _load_fresh(tmp)
    session = "sess-T1"
    args = {"cmd": "git status"}
    output = "nothing to commit"
    warned = False
    for i in range(3):
        rc, out = _run_hook(mod, _make_stdin(session, "Bash", args, output))
        check(f"  exit 0 on call {i + 1}", rc == 0)
        if i < 2:
            check(f"  no warning before 3rd call (call {i + 1})", not _has_warning(out))
        else:
            warned = _has_warning(out)
    check("  3rd identical call fires warning", warned)

    # ── Test 2: 3× same args, DIFFERENT output → no warning (polling guard) ───
    print("== Test 2: same args, different output each time → NO warning ==")
    mod2 = _load_fresh(tmp)
    session2 = "sess-T2"
    args2 = {"cmd": "curl http://localhost:8080/health"}
    outputs = ["status: starting", "status: starting", "status: ready"]
    for i, resp in enumerate(outputs):
        rc, out = _run_hook(mod2, _make_stdin(session2, "Bash", args2, resp))
        check(f"  exit 0 on call {i + 1}", rc == 0)
        check(f"  no warning when output changed (call {i + 1})", not _has_warning(out))

    # ── Test 3: 4th identical call (after already warned at 3rd) still warns ──
    print("== Test 3: 4th identical call also warns ==")
    # Re-use the session from Test 1 (mod already has window with 3 entries)
    rc4, out4 = _run_hook(mod, _make_stdin(session, "Bash", args, output))
    check("  4th identical call warns too", _has_warning(out4))
    check("  exit 0 on 4th call", rc4 == 0)

    # ── Test 4: two sessions are isolated ────────────────────────────────────
    print("== Test 4: session isolation ==")
    mod3 = _load_fresh(tmp)
    sessA = "sess-T4A"
    sessB = "sess-T4B"
    args4 = {"x": "ping"}
    out4_common = "pong"
    # give sessA 3 identical hits
    for _ in range(3):
        _run_hook(mod3, _make_stdin(sessA, "Bash", args4, out4_common))
    # sessB should not be contaminated — first call should not warn
    rc_b, out_b = _run_hook(mod3, _make_stdin(sessB, "Bash", args4, out4_common))
    check("  sessB first call does not warn (isolation)", not _has_warning(out_b))
    check("  sessB exit 0", rc_b == 0)

    # ── Test 5: malformed/empty stdin → exit 0, no output (fail-open) ────────
    print("== Test 5: fail-open on bad input ==")
    mod4 = _load_fresh(tmp)
    for bad_input in ["", "{not valid json", "null", "42"]:
        rc_bad, out_bad = _run_hook(mod4, bad_input)
        check(f"  exit 0 for input={bad_input!r:.20}", rc_bad == 0)
        check(f"  no output for input={bad_input!r:.20}", out_bad.strip() == "")

    # ── Test 6: non-dict tool_input does not crash ────────────────────────────
    print("== Test 6: non-dict tool_input handled gracefully ==")
    mod5 = _load_fresh(tmp)
    session6 = "sess-T6"
    # tool_input is a string, not a dict — some tools send a plain string
    for _ in range(3):
        rc_s, _ = _run_hook(
            mod5,
            json.dumps(
                {
                    "session_id": session6,
                    "tool_name": "Bash",
                    "tool_input": "git diff --stat",  # string, not dict
                    "tool_response": "same output",
                }
            ),
        )
        check("  exit 0 with string tool_input", rc_s == 0)

    # ── Summary ───────────────────────────────────────────────────────────────
    result = "PASS" if not fails else f"FAIL: {', '.join(fails)}"
    print(f"\nRESULT: {result}  ({len(fails)} failures)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
