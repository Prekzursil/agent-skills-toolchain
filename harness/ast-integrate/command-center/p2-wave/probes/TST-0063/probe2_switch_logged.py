#!/usr/bin/env python3
"""Probe 2: the switch is logged; a silent switch is a failing mutant.

Catalog named test: test_the_switch_is_logged
(a silent switch hides the near-miss).

Also AST-checks production dispatchers measure the assembled command line
(or already travel by --prompt-file, which is the conservative form of the
same contract) and re-runs the over-limit case in bash as a second shell.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import cmdline_guard as cg  # noqa: E402

CEILING = cg.WINDOWS_CREATEPROCESS_CHAR_CEILING
VENDOR = [sys.executable, "-B", str(HERE / "vendor_cli.py")]
SWITCH_MARK = cg.SWITCH_EVENT


def fail(reason: str) -> int:
    print(f"FAILED:TST-0063-probe2 {reason}")
    return 1


def test_the_switch_is_logged(root: Path) -> dict:
    payload = cg.pad_payload_for_inline_chars(VENDOR, (), CEILING)
    logged = cg.spawn_guarded(
        VENDOR, payload, workdir=root / "logged", log_switch=True
    )
    silent = cg.spawn_guarded(
        VENDOR, payload, workdir=root / "silent", log_switch=False
    )
    combined_logged = logged.stderr + json.dumps(logged.marshal.log)
    logged_ok = (
        logged.marshal.switched is True
        and logged.exit_code == 0
        and SWITCH_MARK in combined_logged
        and any(e.get("event") == SWITCH_MARK for e in logged.marshal.log)
        and any(e.get("inline_chars") == CEILING for e in logged.marshal.log)
        and any(e.get("ceiling") == CEILING for e in logged.marshal.log)
        and any(e.get("to") == "prompt-file" for e in logged.marshal.log)
    )
    silent_is_bad_state = (
        silent.marshal.switched is True
        and silent.exit_code == 0
        and SWITCH_MARK not in (silent.stderr + json.dumps(silent.marshal.log))
        and not any(e.get("event") == SWITCH_MARK for e in silent.marshal.log)
    )
    under = cg.spawn_guarded(
        VENDOR,
        cg.pad_payload_for_inline_chars(VENDOR, (), CEILING - 1),
        workdir=root / "under-no-log",
        log_switch=True,
    )
    under_silent_ok = (
        under.marshal.switched is False
        and SWITCH_MARK not in (under.stderr + json.dumps(under.marshal.log))
    )
    both_states = logged_ok and silent_is_bad_state and under_silent_ok
    return {
        "id": "test_the_switch_is_logged",
        "pass": both_states,
        "logged_switch_emits_event": logged_ok,
        "silent_switch_mutant_is_detectable": silent_is_bad_state,
        "under_limit_does_not_log_a_switch": under_silent_ok,
        "logged_events": logged.marshal.log,
        "logged_stderr": logged.stderr.strip(),
        "silent_events": silent.marshal.log,
        "silent_stderr": silent.stderr.strip(),
    }


def _uses_prompt_file(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "--prompt-file":
            return True
    return False


def _mentions_measure(src: str) -> bool:
    needles = (
        "windows_cmdline",
        "WINDOWS_CREATEPROCESS_CHAR_CEILING",
        "cmdline_guard",
        "windows_cmdline_chars",
    )
    return any(n in src for n in needles)


def dispatcher_census() -> dict:
    files = [
        "tools/command-center/output_schema_gate.py",
        "tools/command-center/cmdline_guard.py",
        "command-center/p2-wave/probes/ARC-0091/adapter.py",
    ]
    rows = []
    ok = True
    for rel in files:
        path = REPO / rel
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        uses_file = _uses_prompt_file(tree)
        measures = _mentions_measure(src)
        file_ok = path.is_file() and (uses_file or measures)
        ok = ok and file_ok
        rows.append(
            {
                "path": rel,
                "present": True,
                "uses_prompt_file": uses_file,
                "measures_assembled_cmdline": measures,
                "pass": file_ok,
            }
        )
    gate_src = (REPO / "tools/command-center/output_schema_gate.py").read_text(
        encoding="utf-8"
    )
    gate_measures = "windows_cmdline" in gate_src and "WINDOWS_CREATEPROCESS" in gate_src
    ok = ok and gate_measures
    return {"pass": ok, "dispatchers": rows, "output_schema_gate_measures": gate_measures}


def second_shell_rerun() -> dict:
    """Re-run the over-limit marshaller under bash (and pwsh if present)."""
    rel = "command-center/p2-wave/probes/TST-0063/rerun_over_limit.py"
    inner = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {rel}"
    shells = [("bash", ["bash", "-lc", inner])]
    pwsh = shutil.which("pwsh") or shutil.which("pwsh-preview")
    if pwsh:
        shells.append(
            (
                "pwsh",
                [
                    pwsh,
                    "-NoLogo",
                    "-NoProfile",
                    "-Command",
                    inner,
                ],
            )
        )
    results = []
    ok = True
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for name, argv in shells:
        proc = subprocess.run(
            argv,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            check=False,
        )
        text = ((proc.stdout or "") + (proc.stderr or "")).strip()
        shell_ok = proc.returncode == 0 and "prompt-file" in (proc.stdout or "")
        ok = ok and shell_ok
        results.append(
            {
                "shell": name,
                "exit_code": proc.returncode,
                "pass": shell_ok,
                "stdout": (proc.stdout or "").strip()[-500:],
                "stderr_tail": (proc.stderr or "").strip()[-300:],
                "present": True,
            }
        )
    return {
        "pass": ok,
        "pwsh_present": bool(pwsh),
        "shells": results,
        "note": (
            "This worktree is Linux. Bash re-runs the same marshaller. "
            "pwsh is recorded present/absent rather than assumed."
        ),
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0063-p2-") as tmp:
        logged = test_the_switch_is_logged(Path(tmp))
    census = dispatcher_census()
    shells = second_shell_rerun()
    ok = logged["pass"] and census["pass"] and shells["pass"]
    payload = {
        "probe": "probe2-switch-logged",
        "unit_id": "TST-0063",
        "pass": ok,
        "test_the_switch_is_logged": logged,
        "dispatcher_census": census,
        "second_shell": shells,
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    if not ok:
        return fail(
            "switch must be logged; silent mutant must be detectable; "
            "dispatchers must measure or use --prompt-file; "
            "second-shell re-run must switch"
        )
    print(
        "SUCCESS:TST-0063-probe2 switch logged; silent mutant detected; "
        "dispatchers measure or file-transport"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
