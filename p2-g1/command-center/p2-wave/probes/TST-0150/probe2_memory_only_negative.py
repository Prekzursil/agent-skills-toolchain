#!/usr/bin/env python3
"""Probe 2: RAM-only terminal state is detected as lost after monitor death.

Catalog tests_required[1]: negative control — state held only in monitor
memory must be detectable as lost by this test.

A second independent process is launched via bash so the same fingerprint
is recomputed outside this interpreter. pwsh7 is probed and recorded if absent.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path[:] = [p for p in sys.path if p not in ("", ".", str(REPO))]
sys.path.insert(0, str(HERE))

from scenario import canonical, scenario_kill_restart, scenario_memory_only  # noqa: E402

OUT = HERE / "probe2-memory-only.raw.json"
SCENARIO = "command-center/p2-wave/probes/TST-0150/scenario.py"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0150-probe2 {msg}")
    return 1


def run_canonical(argv: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        argv,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def parse_canonical(text: str) -> dict:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            doc = json.loads(line)
            if isinstance(doc, dict):
                return doc
    raise ValueError("no canonical JSON object in subprocess output")


def main() -> int:
    ram = scenario_memory_only()
    durable = scenario_kill_restart()
    rec = ram["reconcile"]
    trust = ram.get("ram_trust_reconcile") or {}
    unknown = list(rec.get("unknown_finished_ids") or [])

    bash = shutil.which("bash") or "/bin/bash"
    bash_cmd = [
        bash,
        "-c",
        (
            "cd "
            + shlex.quote(str(REPO))
            + " && PYTHONDONTWRITEBYTECODE=1 python3 -B "
            + SCENARIO
            + " --canonical-memory"
        ),
    ]
    bash_rc, bash_text = run_canonical(bash_cmd)
    bash_doc: dict | None = None
    bash_err = None
    if bash_rc == 0:
        try:
            bash_doc = parse_canonical(bash_text)
        except (ValueError, json.JSONDecodeError) as exc:
            bash_err = str(exc)
    else:
        bash_err = bash_text[-1500:]

    pwsh = shutil.which("pwsh")
    pwsh_present = pwsh is not None
    pwsh_doc = None
    pwsh_rc = None
    if pwsh_present:
        pwsh_rc, pwsh_text = run_canonical(
            [
                pwsh,
                "-NoProfile",
                "-Command",
                (
                    "Set-Location -LiteralPath '"
                    + str(REPO)
                    + "'; $env:PYTHONDONTWRITEBYTECODE='1'; "
                    "python3 -B "
                    + SCENARIO
                    + " --canonical-memory"
                ),
            ]
        )
        if pwsh_rc == 0:
            try:
                pwsh_doc = parse_canonical(pwsh_text)
            except (ValueError, json.JSONDecodeError):
                pwsh_doc = None

    in_proc = canonical(ram)
    bash_match = bash_doc is not None and bash_doc.get("unknown_finished_ids") == in_proc.get(
        "unknown_finished_ids"
    )

    payload = {
        "probe": "probe2-memory-only-negative",
        "unit_id": "TST-0150",
        "memory_only": in_proc,
        "durable_kill_restart_unknown_count": durable["reconcile"].get("unknown_count"),
        "ram_terminal_before_kill": ram.get("ram_terminal_before_kill"),
        "disk_unknown_ids": unknown,
        "ram_trust_unknown_count": trust.get("unknown_count"),
        "ram_trust_would_pass": trust.get("pass"),
        "second_shell": {
            "bash": bash,
            "bash_rc": bash_rc,
            "bash_match": bash_match,
            "bash_unknown_ids": (bash_doc or {}).get("unknown_finished_ids"),
            "bash_error": bash_err,
            "pwsh_present": pwsh_present,
            "pwsh_rc": pwsh_rc,
            "pwsh_unknown_ids": (pwsh_doc or {}).get("unknown_finished_ids") if pwsh_doc else None,
        },
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))

    if not ram.get("monitor_dead_after_kill"):
        return fail("memory-only path did not raise MonitorDead after kill")
    if sorted(unknown) != ["A", "B"]:
        return fail(f"expected UNKNOWN A,B (RAM-only) got {unknown}")
    if "C" in unknown:
        return fail("durable harvest C was reported UNKNOWN")
    if rec.get("pass") is True:
        return fail("memory-only reconcile passed; RAM loss was not detected")
    if trust.get("pass") is not True:
        return fail("pre-kill RAM snapshot did not reconcile cleanly (vacuous negative)")
    if (trust.get("unknown_count") or 0) != 0:
        return fail("RAM-trust check did not stay silent on the stale snapshot")
    if durable["reconcile"].get("unknown_count") != 0:
        return fail("durable kill+restart grew UNKNOWNs; contrast is broken")
    ram_before = ram.get("ram_terminal_before_kill") or {}
    if ram_before.get("A") not in {"harvested", "remote_completed"}:
        return fail(f"A was not terminal in RAM before kill: {ram_before}")
    if ram_before.get("B") not in {"harvested", "remote_completed"}:
        return fail(f"B was not terminal in RAM before kill: {ram_before}")
    if bash_rc != 0 or not bash_match:
        return fail(f"bash second-shell mismatch rc={bash_rc} err={bash_err} doc={bash_doc}")

    print(
        "SUCCESS:TST-0150-probe2 memory-only UNKNOWN=A,B detected; "
        f"ram_trust_silent={trust.get('pass')} bash_match={bash_match} "
        f"pwsh_present={pwsh_present}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
