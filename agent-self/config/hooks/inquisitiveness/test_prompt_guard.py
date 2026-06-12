#!/usr/bin/env python
"""Self-contained tests for prompt-guard.py. Run: python test_prompt_guard.py
Uses subprocess to drive the hook exactly as the harness does (stdin JSON, stdout parse).
No external dependencies (stdlib only)."""
from __future__ import annotations

import importlib
import importlib.util
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
fails: list[str] = []


def check(name: str, cond: bool) -> None:
    print(f"  {'OK ' if cond else 'BAD'}  {name}")
    if not cond:
        fails.append(name)


def run_guard(stdin_obj: dict) -> tuple[int, dict | None]:
    """Load prompt-guard.py as a module, feed it the JSON via stdin, capture stdout.
    Returns (exit_code, parsed_payload_or_None)."""
    spec = importlib.util.spec_from_file_location("prompt_guard", HERE / "prompt-guard.py")
    mod = importlib.util.module_from_spec(spec)
    old_stdin, old_stdout = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(json.dumps(stdin_obj))
    cap = io.StringIO()
    sys.stdout = cap
    try:
        spec.loader.exec_module(mod)
        rc = mod.main()
    finally:
        sys.stdin, sys.stdout = old_stdin, old_stdout
    output = cap.getvalue().strip()
    payload = None
    if output:
        try:
            payload = json.loads(output.splitlines()[-1])
        except Exception:
            pass
    return rc, payload


def _has_guidance(payload: dict | None) -> bool:
    """Return True if the payload injects additionalContext guidance."""
    if payload is None:
        return False
    ctx = payload.get("hookSpecificOutput", {}).get("additionalContext", "")
    return bool(ctx) and "Inquisitiveness Guard" in ctx


def main() -> int:
    print("== bypass: '*' prefix never injects ==")
    rc, p = run_guard({"prompt": "* fix everything", "cwd": "."})
    check("exit 0 on bypass", rc == 0)
    check("no injection on '*' prefix", not _has_guidance(p))

    print("== clearly vague prompts DO inject ==")

    # Short + vague verb + pronoun + no concrete token
    rc, p = run_guard({"prompt": "fix it", "cwd": "."})
    check("exit 0 always (vague prompt)", rc == 0)
    check("'fix it' injects guidance", _has_guidance(p))

    rc, p = run_guard({"prompt": "improve this", "cwd": "."})
    check("exit 0 (improve this)", rc == 0)
    check("'improve this' injects guidance", _has_guidance(p))

    rc, p = run_guard({"prompt": "make it better", "cwd": "."})
    check("exit 0 (make it better)", rc == 0)
    check("'make it better' injects guidance", _has_guidance(p))

    print("== clear/specific prompts do NOT inject ==")

    # Names a specific file
    rc, p = run_guard({"prompt": "Fix the off-by-one error in ledger.py line 83 where seq wraps", "cwd": "."})
    check("exit 0 (specific)", rc == 0)
    check("specific file+line does NOT inject", not _has_guidance(p))

    # Names an error
    rc, p = run_guard({
        "prompt": "There is a KeyError exception in auth.py when the token is missing — add a default fallback",
        "cwd": "."
    })
    check("exit 0 (error ref)", rc == 0)
    check("error reference does NOT inject", not _has_guidance(p))

    # URL in prompt
    rc, p = run_guard({"prompt": "Fetch https://api.example.com/status and parse the JSON response", "cwd": "."})
    check("exit 0 (URL)", rc == 0)
    check("URL in prompt does NOT inject", not _has_guidance(p))

    # Long, well-specified prompt
    rc, p = run_guard({
        "prompt": (
            "Add a new endpoint POST /api/users that validates the email field, "
            "hashes the password with bcrypt, persists to the users table, and returns 201 with the user id"
        ),
        "cwd": "."
    })
    check("exit 0 (long specific)", rc == 0)
    check("long specific prompt does NOT inject", not _has_guidance(p))

    print("== fail-open: malformed / empty stdin does not raise ==")
    spec = importlib.util.spec_from_file_location("prompt_guard_fo", HERE / "prompt-guard.py")
    mod2 = importlib.util.module_from_spec(spec)
    old_stdin, old_stdout = sys.stdin, sys.stdout
    sys.stdin = io.StringIO("")  # empty stdin
    cap2 = io.StringIO()
    sys.stdout = cap2
    try:
        spec.loader.exec_module(mod2)
        rc_fo = mod2.main()
    except Exception as ex:
        rc_fo = -1
        print(f"    (raised: {ex})")
    finally:
        sys.stdin, sys.stdout = old_stdin, old_stdout
    check("exit 0 on empty stdin (fail-open)", rc_fo == 0)

    print("== additionalContext format ==")
    rc, p = run_guard({"prompt": "improve everything", "cwd": "."})
    if p is not None:
        hso = p.get("hookSpecificOutput", {})
        check("hookEventName = UserPromptSubmit", hso.get("hookEventName") == "UserPromptSubmit")
        check("additionalContext is a non-empty string", isinstance(hso.get("additionalContext"), str) and len(hso["additionalContext"]) > 20)
        check("mentions clarify-requirements skill", "clarify-requirements" in hso.get("additionalContext", ""))
    else:
        check("payload present for vague prompt", False)
        check("hookEventName present", False)
        check("additionalContext present", False)

    print(f"\nRESULT: {'PASS' if not fails else 'FAIL: ' + ', '.join(fails)}  "
          f"({len(fails)} failures / {13 - len(fails)} passed)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
