#!/usr/bin/env python3
"""Direct-invocation tests for tool-result-sentinel/sentinel.py.

Proves the hook FIRES on FAILED/AMBIGUOUS results, stays SILENT on SUCCESS,
and THROTTLES a repeated identical failure. Stdlib only; no pytest required.

Run:  python test_sentinel.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

HOOK = str(Path(__file__).resolve().parent / "sentinel.py")


def run(payload: dict, env_extra: dict | None = None) -> str:
    env = dict(os.environ)
    # Isolate the warned-fingerprint store per test run.
    env.setdefault("TOOL_SENTINEL_ROOT", str(Path(tempfile.gettempdir()) / f"ts-test-{uuid.uuid4().hex}"))
    if env_extra:
        env.update(env_extra)
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=env, timeout=20)
    assert p.returncode == 0, f"hook must exit 0, got {p.returncode}: {p.stderr}"
    return p.stdout.strip()


def fired(out: str) -> bool:
    if not out:
        return False
    try:
        return "additionalContext" in json.loads(out).get("hookSpecificOutput", {})
    except Exception:
        return False


def main() -> int:
    sid = "test-sentinel-1"
    root = str(Path(tempfile.gettempdir()) / f"ts-test-{uuid.uuid4().hex}")
    env = {"TOOL_SENTINEL_ROOT": root}
    cases = []

    # 1. MCP isError envelope -> FIRES (FAILED)
    out = run({"session_id": sid, "tool_name": "mcp__basic-memory__write_note",
               "tool_input": {"title": "x"},
               "tool_response": {"content": [{"type": "text", "text": "boom"}], "isError": True}}, env)
    cases.append(("MCP isError=true fires", fired(out), True, out))

    # 2. MCP infra-failure phrase -> FIRES (FAILED)
    out = run({"session_id": "s2", "tool_name": "mcp__basic-memory__search_notes",
               "tool_input": {"q": "a"},
               "tool_response": "Error: Could not connect to basic-memory server (connection refused)"}, env)
    cases.append(("MCP 'could not connect' fires", fired(out), True, out))

    # 3. Bash non-zero exit -> FIRES (FAILED)
    out = run({"session_id": "s3", "tool_name": "Bash",
               "tool_input": {"command": "false"},
               "tool_response": {"stdout": "", "stderr": "nope", "exit_code": 1}}, env)
    cases.append(("Bash exit_code=1 fires", fired(out), True, out))

    # 4. Bash exit 0 whose OUTPUT contains 'error' -> SILENT (structural-only for Bash)
    out = run({"session_id": "s4", "tool_name": "Bash",
               "tool_input": {"command": "grep error log"},
               "tool_response": {"stdout": "2 errors found in log\nconnection refused", "exit_code": 0}}, env)
    cases.append(("Bash exit0 w/ 'error' in stdout is SILENT", fired(out), False, out))

    # 5. Clean MCP success -> SILENT
    out = run({"session_id": "s5", "tool_name": "mcp__ghidra-mcp__decompile_function",
               "tool_input": {"name": "main"},
               "tool_response": {"content": [{"type": "text", "text": "int main(){...}"}]}}, env)
    cases.append(("clean MCP success is SILENT", fired(out), False, out))

    # 6. MCP must-return-content but EMPTY -> FIRES (AMBIGUOUS)
    out = run({"session_id": "s6", "tool_name": "mcp__ghidra-mcp__decompile_function",
               "tool_input": {"name": "ghost"},
               "tool_response": {"content": []}}, env)
    cases.append(("MCP empty decompile is AMBIGUOUS fires", fired(out), True, out))

    # 7. MCP list_ returning [] -> SILENT (empty is a valid answer)
    out = run({"session_id": "s7", "tool_name": "mcp__ghidra-mcp__list_methods",
               "tool_input": {}, "tool_response": "[]"}, env)
    cases.append(("MCP list_ empty is SILENT", fired(out), False, out))

    # 8. THROTTLE: same failing (tool,args) twice -> 1st fires, 2nd silent
    pay = {"session_id": "s8-throttle", "tool_name": "mcp__x__y",
           "tool_input": {"a": 1}, "tool_response": {"isError": True, "content": [{"text": "e"}]}}
    out1 = run(pay, env)
    out2 = run(pay, env)  # identical -> throttled
    cases.append(("throttle: 1st identical failure fires", fired(out1), True, out1))
    cases.append(("throttle: 2nd identical failure SILENT", fired(out2), False, out2))

    # 9. DISABLED env -> SILENT even on failure
    out = run({"session_id": "s9", "tool_name": "mcp__x__y", "tool_input": {},
               "tool_response": {"isError": True}}, {"TOOL_SENTINEL": "off", **env})
    cases.append(("TOOL_SENTINEL=off is SILENT", fired(out), False, out))

    ok = True
    for name, got, want, out in cases:
        status = "PASS" if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"[{status}] {name}: fired={got} expected={want}")
        if got != want:
            print(f"         output={out!r}")
    print("\nFIRED-sample (case 1):")
    print(run({"session_id": "demo", "tool_name": "mcp__basic-memory__write_note",
               "tool_input": {"title": "x"}, "tool_response": {"isError": True}},
              {"TOOL_SENTINEL_ROOT": str(Path(tempfile.gettempdir()) / f"ts-demo-{uuid.uuid4().hex}")}))
    print("SILENT-sample (clean Bash): " + repr(run(
        {"session_id": "demo2", "tool_name": "Bash", "tool_input": {"command": "ls"},
         "tool_response": {"stdout": "a\nb", "exit_code": 0}},
        {"TOOL_SENTINEL_ROOT": str(Path(tempfile.gettempdir()) / f"ts-demo-{uuid.uuid4().hex}")})))
    print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
