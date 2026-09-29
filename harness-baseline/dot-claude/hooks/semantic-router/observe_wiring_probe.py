#!/usr/bin/env python
"""BOTH-STATES wiring probe for hooks/semantic-router/observe.py.

observe.py is the PostToolUse half of the router's suggested-vs-used loop: route.py does
``suggested++`` and observe.py does ``used++``. With observe.py unwired, ``used`` can never
advance, so ``success.boost()`` returns 0.0 for every key and the loop is open.

Asserts, all fail-closed:

  1. WIRING   -- some ``hooks.PostToolUse`` command mentions ``observe.py``, and its matcher
                 covers Skill / Task / mcp__* (the three key-shapes observe.py can credit).
  2. CREDITS  -- a PostToolUse payload for a tool that WAS suggested this session advances
                 ``used`` by exactly 1 in an isolated store.
  3. REFUSES  -- the same payload carrying an explicit failure marker (``isError: true``)
                 advances ``used`` by 0.

2 and 3 run the command settings.json names, in a redirected HOME so the real
``success.json`` is never touched.

Exit 0 = all pass. Exit 1 = a state is wrong, with the reason named.

Usage:  python observe_wiring_probe.py [path-to-settings.json]
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

THIS = Path(__file__).resolve().parent
DEFAULT_SETTINGS = Path.home() / ".claude" / "settings.json"
NEEDLE = "observe.py"
SID = "observe-wiring-probe"


def _post_tool_use(settings_path: Path) -> list[tuple[str, str]]:
    """[(matcher, command)] for every PostToolUse command hook."""
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    out: list[tuple[str, str]] = []
    for group in (data.get("hooks") or {}).get("PostToolUse") or []:
        matcher = str((group or {}).get("matcher") or "")
        for entry in (group or {}).get("hooks") or []:
            cmd = (entry or {}).get("command")
            if isinstance(cmd, str):
                out.append((matcher, cmd))
    return out


def _seed_session(store_dir: Path, key: str) -> None:
    """Pretend route.py already suggested `key` this session (observe only credits suggestions)."""
    store_dir.mkdir(parents=True, exist_ok=True)
    (store_dir / f"{SID}.json").write_text(json.dumps({"pending": [key], "credited": []}), encoding="utf-8")


def _used(success_json: Path, key: str) -> int:
    try:
        return int((json.loads(success_json.read_text(encoding="utf-8")).get(key) or {}).get("used", 0))
    except Exception:  # noqa: BLE001
        return 0


def _run_once(cmd: str, payload: dict, sandbox: Path) -> tuple[int, int]:
    """Run the wired command in an isolated store. Returns (exit_code, used_after)."""
    key = "mcp:tavily"
    work = sandbox / "hook"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    # observe.py imports success.py from its OWN directory, and success.py resolves both the
    # durable store and the per-session dir relative to that copy -- so copy the module pair
    # into a sandbox and point TMPDIR at it. Nothing touches the live success.json.
    for name in ("observe.py", "success.py"):
        shutil.copy2(THIS / name, work / name)
    success_json = work / "success.json"
    success_json.write_text(json.dumps({key: {"suggested": 3, "used": 0}}), encoding="utf-8")

    tmp = sandbox / "tmp"
    tmp.mkdir(exist_ok=True)
    _seed_session(tmp / "semantic-router", key)

    env = dict(os.environ)
    env["TMPDIR"] = env["TEMP"] = env["TMP"] = str(tmp)
    sandboxed_cmd = cmd.replace(str(THIS).replace("\\", "/"), str(work).replace("\\", "/"))
    if "observe.py" not in sandboxed_cmd or str(work).replace("\\", "/") not in sandboxed_cmd:
        # Path substitution failed -> fall back to invoking the sandbox copy directly rather
        # than silently testing the live module.
        sandboxed_cmd = f'"{sys.executable}" "{work / "observe.py"}"'
    proc = subprocess.run(
        sandboxed_cmd, shell=True, input=json.dumps(payload), capture_output=True, text=True, timeout=60, env=env
    )
    return proc.returncode, _used(success_json, key)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    settings = Path(argv[0]) if argv else DEFAULT_SETTINGS
    if not settings.exists():
        print(f"FAILED:observe-wiring settings.json not found at {settings}")
        return 1
    try:
        entries = _post_tool_use(settings)
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:observe-wiring settings.json unparseable ({type(exc).__name__})")
        return 1
    if not entries:
        print("FAILED:observe-wiring no PostToolUse commands found at all")
        return 1

    wired = [(m, c) for m, c in entries if NEEDLE in c]
    print(f"PostToolUse commands: {len(entries)}; mentioning '{NEEDLE}': {len(wired)}")
    if not wired:
        print("FAILED:observe-wiring WIRING=ABSENT -- observe.py is not reachable from settings.json")
        return 1
    matcher, cmd = wired[0]
    print(f"WIRED matcher: {matcher}")
    print(f"WIRED command: {cmd}")

    bad = []
    for shape in ("Skill", "Task", "mcp__"):
        if shape not in matcher:
            bad.append(f"matcher does not cover {shape!r} -- observe.py can never credit that key-shape")

    ok_payload = {
        "hook_event_name": "PostToolUse",
        "session_id": SID,
        "tool_name": "mcp__tavily__tavily_search",
        "tool_input": {"query": "x"},
        "tool_response": {"content": [{"type": "text", "text": "ok"}]},
    }
    fail_payload = dict(ok_payload)
    fail_payload["tool_response"] = {"isError": True, "content": [{"type": "text", "text": "not connected"}]}

    with tempfile.TemporaryDirectory() as td:
        sandbox = Path(td)
        rc_ok, used_ok = _run_once(cmd, ok_payload, sandbox)
        rc_bad, used_bad = _run_once(cmd, fail_payload, sandbox)

    if rc_ok != 0:
        bad.append(f"success-state exit={rc_ok} (must be 0; observe.py is inject-nothing/fail-open)")
    if used_ok != 1:
        bad.append(f"success-state credited used={used_ok}, expected 1")
    else:
        print(f"STATE 1 CREDITS exit={rc_ok} used 0 -> {used_ok} for a suggested, successful mcp call")

    if rc_bad != 0:
        bad.append(f"failure-state exit={rc_bad} (must be 0)")
    if used_bad != 0:
        bad.append(f"failure-state credited used={used_bad} on an isError payload, expected 0")
    else:
        print(f"STATE 2 REFUSES exit={rc_bad} used stayed {used_bad} for an explicitly-failed call")

    if bad:
        for b in bad:
            print(f"  - {b}")
        print(f"FAILED:observe-wiring {len(bad)} assertion(s) failed")
        return 1
    print("SUCCESS:observe-wiring wired at PostToolUse + credits a real use + refuses a failed one")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
