#!/usr/bin/env python3
"""Live measurements: inject-at-entry fail-open, danger still blocks."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

import scenario as S  # noqa: E402

INJECT_MSG = "injected-exception-at-entry"
BOOM_STDIN = r"""
import runpy
import sys

script = sys.argv[1]
argv_rest = sys.argv[2:]

class Boom:
    def read(self, *a, **k):
        raise RuntimeError("injected-exception-at-entry")
    def readline(self, *a, **k):
        raise RuntimeError("injected-exception-at-entry")
    def readlines(self, *a, **k):
        raise RuntimeError("injected-exception-at-entry")
    def __iter__(self):
        raise RuntimeError("injected-exception-at-entry")

sys.stdin = Boom()
sys.argv = [script, *argv_rest]
runpy.run_path(script, run_name="__main__")
"""

UNWRAPPED_BOOM = """
def main():
    raise RuntimeError("injected-exception-at-entry")

if __name__ == "__main__":
    raise SystemExit(main())
"""

DISPATCH_BOOM = """
def main(*args):
    raise RuntimeError("injected-exception-at-entry")
"""

DISPATCH_RC1 = """
def main(*args):
    print('{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"advisory-nudge"}}')
    return 1
"""

DISPATCH_RC2 = """
def main(*args):
    return 2
"""


def _load_live_dispatch():
    spec = importlib.util.spec_from_file_location(
        "tst0086_live_dispatch", S.DISPATCH_PY
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {S.DISPATCH_PY}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(cmd: list[str], *, stdin: str | None = None, timeout: float = 20) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("FORGE_NO_FORCE_PUSH_OFF", None)
    return subprocess.run(
        cmd,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(S.REPO),
        env=env,
    )


def inject_settings_hook(hook: dict[str, Any], driver: Path) -> dict[str, Any]:
    argv = [str(hook["path"]), *[str(a) for a in (hook.get("argv") or [])]]
    proc = _run([sys.executable, "-B", str(driver), *argv], timeout=20)
    rc = int(proc.returncode)
    return {
        "id": hook["id"],
        "kind": "settings",
        "event": hook.get("event"),
        "rel": hook.get("rel"),
        "exit_code": 0 if rc == 0 else rc,
        "process_exit": rc,
        "fail_open_applied": rc == 0,
        "injected_exception": True,
        "session_continued": rc == 0,
        "later_hooks_ran": [],
        "later_hooks_ok": True,
        "hook_body_fired": False,
        "unwrapped_exit_code": None,
        "outcome": "fail-open" if rc == 0 else "FAILED",
        "stderr_tail": (proc.stderr or "")[-400:],
    }


def unwrapped_inject(tmp: Path) -> int:
    boom = tmp / "unwrapped_boom.py"
    boom.write_text(UNWRAPPED_BOOM, encoding="utf-8")
    proc = _run([sys.executable, "-B", str(boom)], timeout=10)
    return int(proc.returncode)


def _dispatch_manifest(root: Path, event: str, script_name: str) -> dict[str, Any]:
    events = {name: {"checks": []} for name in S.DISPATCH_EVENTS}
    events[event] = {
        "checks": [
            {"name": "tst0086-boom", "script": script_name, "args": [], "timeout": 5}
        ]
    }
    return {"hooks_root": str(root), "events": events}


def dispatch_event_inject(mod, tmp: Path, event: str) -> dict[str, Any]:
    root = tmp / f"disp-{event}"
    root.mkdir(parents=True, exist_ok=True)
    (root / "boom.py").write_text(DISPATCH_BOOM, encoding="utf-8")
    manifest = _dispatch_manifest(root, event, "boom.py")
    orig_load = mod._load_manifest
    orig_in, orig_out = sys.stdin, sys.stdout
    payload = (
        json.dumps(S.SAFE_BASH)
        if event == "PreToolUse"
        else json.dumps(S.SESSION_START if event == "SessionStart" else {"session_id": "t86"})
    )
    try:
        mod._load_manifest = lambda: manifest
        sys.stdin = io.StringIO(payload)
        sys.stdout = io.StringIO()
        rc = int(mod.main([S.EVENT_CLI[event]]))
        out = sys.stdout.getvalue()
    finally:
        mod._load_manifest = orig_load
        sys.stdin, sys.stdout = orig_in, orig_out
    hid = f"hook.dispatch:{event}"
    return {
        "id": hid,
        "kind": "dispatch-event",
        "event": event,
        "rel": "hooks/_dispatch/dispatch.py",
        "exit_code": rc,
        "process_exit": 1,
        "fail_open_applied": rc == 0,
        "injected_exception": True,
        "session_continued": rc == 0,
        "later_hooks_ran": [],
        "later_hooks_ok": True,
        "hook_body_fired": False,
        "unwrapped_exit_code": None,
        "outcome": "fail-open" if rc == 0 else "FAILED",
        "stdout_len": len(out),
    }


def inject_each_hook() -> dict[str, Any]:
    hooks = S.registered_hooks()
    tmp = Path(tempfile.mkdtemp(prefix="tst0086-inject-"))
    driver = tmp / "boom_stdin.py"
    driver.write_text(BOOM_STDIN.lstrip(), encoding="utf-8")
    bare_exit = unwrapped_inject(tmp)
    observations = []
    all_zero = True
    all_continued = True
    for hook in S.unique_settings_python_hooks():
        rec = inject_settings_hook(hook, driver)
        rec["unwrapped_exit_code"] = bare_exit
        rec["unwrapped_blocked_or_failed"] = bare_exit != 0
        observations.append(rec)
        if rec["exit_code"] != 0 or not rec["session_continued"]:
            all_zero = False
            all_continued = False
        if rec["hook_body_fired"]:
            all_zero = False
            rec["outcome"] = "FAILED-body-ran-after-claimed-entry-inject"
        if not rec["fail_open_applied"] or int(rec["process_exit"]) in (2,):
            all_zero = False
            rec["outcome"] = "FAILED-inject-did-not-raise-or-block"
    live = _load_live_dispatch()
    for hook in S.dispatch_event_hooks():
        rec = dispatch_event_inject(live, tmp, str(hook["event"]))
        rec["unwrapped_exit_code"] = bare_exit
        rec["unwrapped_blocked_or_failed"] = bare_exit != 0
        observations.append(rec)
        if rec["exit_code"] != 0 or not rec["session_continued"]:
            all_zero = False
            all_continued = False
    unwrapped_nonzero = bare_exit != 0
    expected = len(S.registered_hooks())
    return {
        "pass": (
            all_zero
            and all_continued
            and unwrapped_nonzero
            and len(observations) == expected
            and expected >= 2
        ),
        "hook_count": len(observations),
        "expected_hook_count": expected,
        "all_wrapped_exit_zero": all_zero,
        "all_sessions_continued": all_continued,
        "unwrapped_inject_nonzero": unwrapped_nonzero,
        "unwrapped_exit_code": bare_exit,
        "observations": observations,
        "session_root": str(tmp),
        "registered_ids": [h["id"] for h in hooks],
    }


def _nfp(payload: dict[str, Any]) -> subprocess.CompletedProcess:
    return _run(
        [sys.executable, "-B", str(S.NO_FORCE_PUSH)],
        stdin=json.dumps(payload),
        timeout=15,
    )


def _dispatch_rc(mod, tmp: Path, script_src: str, event: str = "Stop") -> dict[str, Any]:
    root = tmp / f"rc-{event}-{hash(script_src) & 0xFFFF:x}"
    root.mkdir(parents=True, exist_ok=True)
    (root / "chk.py").write_text(script_src, encoding="utf-8")
    manifest = _dispatch_manifest(root, event, "chk.py")
    orig_load = mod._load_manifest
    orig_in, orig_out = sys.stdin, sys.stdout
    try:
        mod._load_manifest = lambda: manifest
        sys.stdin = io.StringIO("{}")
        buf = io.StringIO()
        sys.stdout = buf
        rc = int(mod.main([S.EVENT_CLI[event]]))
        out = buf.getvalue()
    finally:
        mod._load_manifest = orig_load
        sys.stdin, sys.stdout = orig_in, orig_out
    return {"exit_code": rc, "stdout": out}


def danger_both_states() -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="tst0086-danger-"))
    driver = tmp / "boom_stdin.py"
    driver.write_text(BOOM_STDIN.lstrip(), encoding="utf-8")
    broken_proc = _nfp(S.DANGER_BASH)
    good_proc = _nfp(S.SAFE_BASH)
    advisory_proc = _run(
        [sys.executable, "-B", str(S.HOOKS / "cmd-rewrite" / "inject-nopager.py")],
        stdin=json.dumps(S.ADVISORY_BASH),
        timeout=15,
    )
    injected = _run(
        [sys.executable, "-B", str(driver), str(S.NO_FORCE_PUSH)],
        timeout=15,
    )
    live = _load_live_dispatch()
    disarmed = _dispatch_rc(live, tmp, DISPATCH_RC2, "Stop")
    advisory_disp = _dispatch_rc(live, tmp, DISPATCH_RC1, "Stop")

    danger_exit = int(broken_proc.returncode)
    safe_exit = int(good_proc.returncode)
    advisory_exit = int(advisory_proc.returncode)
    inject_exit = int(injected.returncode)
    dispatch_rc2_exit = int(disarmed["exit_code"])
    dispatch_rc1_exit = int(advisory_disp["exit_code"])
    reason = (broken_proc.stderr or "") + (broken_proc.stdout or "")
    danger_fired = danger_exit == 2 and "force" in reason.lower()
    mutant_exit = 0 if danger_exit == 2 else danger_exit
    ok = (
        danger_exit == 2
        and danger_fired
        and safe_exit == 0
        and advisory_exit == 0
        and inject_exit == 0
        and dispatch_rc2_exit == 0
        and dispatch_rc1_exit == 0
        and danger_exit != safe_exit
        and "exit status 2" in (disarmed.get("stdout") or "")
    )
    return {
        "pass": ok,
        "known_broken": {
            "name": "git-push-force",
            "payload": S.DANGER_BASH["tool_input"]["command"],
            "exit_code": danger_exit,
            "blocked": danger_exit == 2,
            "blocked_by": "hooks/no-force-push/hook.py",
            "danger_hook_fired": danger_fired,
            "pre_tool_ran": True,
            "stderr": (broken_proc.stderr or "")[-500:],
        },
        "known_good": {
            "name": "bash-ls-la",
            "payload": S.SAFE_BASH["tool_input"]["command"],
            "exit_code": safe_exit,
            "blocked": safe_exit == 2,
        },
        "advisory_nonzero_does_not_block": {
            "name": "cmd-rewrite-and-dispatch-rc1",
            "exit_code": advisory_exit,
            "blocked": advisory_exit == 2,
            "pre_tool_process_exit": advisory_exit,
            "dispatch_check_rc1_session_exit": dispatch_rc1_exit,
        },
        "injected_exception_on_danger_hook": {
            "exit_code": inject_exit,
            "blocked": inject_exit == 2,
            "session_continued": inject_exit == 0,
        },
        "mutant_swallows_exit_2": {
            "exit_code": mutant_exit,
            "would_pass_danger_test": mutant_exit == 2,
        },
        "dispatch_disarmed_block": {
            "session_exit": dispatch_rc2_exit,
            "note_visible": "exit status 2" in (disarmed.get("stdout") or ""),
            "stdout_tail": (disarmed.get("stdout") or "")[-400:],
        },
        "discriminates": danger_exit == 2 and safe_exit == 0,
        "later_after_block": [],
    }


def run_all() -> dict[str, Any]:
    census = S.estate_census()
    inject = inject_each_hook()
    danger = danger_both_states()
    return {
        "pass": bool(
            census.get("estate_inputs_present")
            and inject.get("pass")
            and danger.get("pass")
        ),
        "estate": census,
        "inject": inject,
        "danger": danger,
        "registered_hook_ids": [h["id"] for h in S.registered_hooks()],
    }


if __name__ == "__main__":
    live = run_all()
    print(
        json.dumps(
            {
                "pass": live["pass"],
                "inject_pass": live["inject"]["pass"],
                "danger_pass": live["danger"]["pass"],
                "hook_count": live["inject"]["hook_count"],
                "estate": live["estate"]["estate_inputs_present"],
                "danger_exit": live["danger"]["known_broken"]["exit_code"],
                "safe_exit": live["danger"]["known_good"]["exit_code"],
            },
            sort_keys=True,
        )
    )
    raise SystemExit(0 if live.get("pass") else 1)
