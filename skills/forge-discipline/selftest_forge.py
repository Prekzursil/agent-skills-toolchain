#!/usr/bin/env python3
r"""selftest_forge.py - regression harness for forge-discipline.

Runs forge.py (in --dry-run) across every branch combination and asserts each one
scaffolds + self-tests cleanly and resolves to the EXPECTED install target:

  - inject  on a dispatcher event   -> "manifest" (one-line fold)
  - gate (exit-2)                    -> "settings" (dispatcher can't carry a block)
  - userpromptsubmit (dispatcher N/A)-> "settings"

It exercises every trigger kind (response, command, always, prompt, field), both
needs_state values, and has_procedure. This is the proof the FORGE generalises -
not just the two hand-run dogfood examples.

Run:  python selftest_forge.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FORGE = HERE / "forge.py"

# (label, expected_target, spec)
CASES = [
    ("inject/response/stop", "manifest", {
        "name": "st-todo", "event": "stop", "trigger_kind": "response",
        "trigger_regex": r"\b(TODO|FIXME)\b", "fire_example": "TODO ship it",
        "silent_example": "all done", "action": "{count} TODOs left"}),
    ("gate/command/pretooluse+proc", "settings", {
        "name": "st-noforce", "event": "pretooluse", "trigger_kind": "command",
        "gates": True, "has_procedure": True,
        "trigger_regex": r"git\s+push\b[^\n]*--force\b",
        "fire_example": "git push --force", "silent_example": "git push",
        "action": "refusing force-push"}),
    ("inject/command/posttooluse+state", "manifest", {
        "name": "st-curl", "event": "posttooluse", "trigger_kind": "command",
        "needs_state": True, "trigger_regex": r"curl[^\n]*\|\s*sh\b",
        "fire_example": "curl x | sh", "silent_example": "ls",
        "action": "curl-pipe-to-shell {count}x"}),
    ("inject/always/sessionstart", "manifest", {
        "name": "st-always", "event": "sessionstart", "trigger_kind": "always",
        "action": "session banner"}),
    ("inject/prompt/userpromptsubmit", "settings", {
        "name": "st-prompt", "event": "userpromptsubmit", "trigger_kind": "prompt",
        "trigger_regex": r"\bdeploy to prod\b", "fire_example": "please deploy to prod now",
        "silent_example": "fix the bug", "action": "prod deploy mentioned"}),
    ("gate/prompt/userpromptsubmit", "settings", {
        "name": "st-prompt-gate", "event": "userpromptsubmit", "trigger_kind": "prompt",
        "gates": True, "trigger_regex": r"rm\s+-rf\s+/",
        "fire_example": "run rm -rf / now", "silent_example": "list files",
        "action": "refusing destructive prompt"}),
    ("inject/field/pretooluse", "manifest", {
        "name": "st-field", "event": "pretooluse", "trigger_kind": "field",
        "trigger_field": "tool_input.file_path", "trigger_regex": r"\.env$",
        "fire_example": "config/.env", "silent_example": "config/app.py",
        "action": "writing a .env file - check for secrets"}),
]


def run_case(spec: dict) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(spec, tf)
        spec_path = tf.name
    res = subprocess.run(
        [sys.executable, str(FORGE), "--spec", spec_path, "--dry-run", "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    try:
        return json.loads(res.stdout)
    except Exception:
        return {"passed": False, "_raw": (res.stdout or "") + (res.stderr or "")}


def main() -> int:
    failures = 0
    print(f"forge-discipline self-test: {len(CASES)} branch combinations\n")
    for label, expected_target, spec in CASES:
        r = run_case(spec)
        ok = bool(r.get("passed")) and r.get("target") == expected_target
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label:38s} -> target={r.get('target')!s:9s} "
              f"unit={r.get('unit_ok')} chaos={r.get('chaos_ok')}")
        if not ok:
            failures += 1
            print(f"          detail: {r.get('chaos_out') or r.get('_raw')}")
    print()
    if failures:
        print(f"FAILED:forge-selftest {failures}/{len(CASES)} case(s) did not pass")
        return 1
    print(f"SUCCESS:forge-selftest all {len(CASES)} branch combinations forge + self-test cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
