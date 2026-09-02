#!/usr/bin/env python3
"""Probe 2: live cell, cross-shell naming, .cmd disagreement, unmodelled cmd.exe.

Mechanically different from probe 1 (which runs the unittest matrix). This
probe executes the diagnostics command live, injects pwsh7 and Git Bash
identities, plants a .cmd shim, and checks the catalog receipt.
"""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools/plugin"
sys.path.insert(0, str(PLUGIN))
import compat_diagnostics as cd  # noqa: E402

RECEIPT = REPO / "command-center/receipts/IMP-0046.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0046-probe2 {msg}")
    return 1


def main() -> int:
    live = cd.build_report()
    measured = live["measured_from_shell"]["name"]
    print(f"live_shell={measured} live_verdict={live['verdict']}")
    print(
        f"live_cell client={live['cell']['client']['name']}/"
        f"{live['cell']['client']['version']} "
        f"os={live['cell']['os']['name']} shell={live['cell']['shell']['name']}"
    )
    if measured not in {"bash", "sh", "zsh", "pwsh7", "git-bash", "wsl-bash"}:
        return fail(f"live measured_from_shell is not a modelled shell: {measured!r}")
    if live["cell"]["os"]["name"] != "linux":
        return fail("expected linux OS on this runner")

    for identity in ("pwsh7", "git-bash"):
        inj = {
            "shell": identity,
            "shell_version": "injected-for-cross-shell",
            "client_name": "cursor",
            "client_version": "2026.08.11",
            "os_name": "linux",
            "os_build": "probe2",
            "interpreter_versions": {
                "python3": "3.12.3",
                "node": "24.5.0",
                "bash": "5.2.21",
                "pwsh": "7.4.0" if identity == "pwsh7" else None,
            },
        }
        report = cd.build_report(inject=inj)
        named = report["measured_from_shell"]["name"]
        print(f"injected_{identity}_measured_from={named} verdict={report['verdict']}")
        if named != identity:
            return fail(f"injected {identity} was reported as {named}")

    with tempfile.TemporaryDirectory() as td:
        shim = Path(td) / "mystery-tool.cmd"
        shim.write_text("@echo off\n", encoding="utf-8")
        os.chmod(shim, stat.S_IRUSR | stat.S_IWUSR)
        rec = cd.dual_resolve("mystery-tool", [td])
        print(
            f"cmd_shim posix={rec['posix_which']!r} "
            f"get_command={rec['win_get_command']!r} disagree={rec['disagree']}"
        )
        if rec["posix_which"] is not None:
            return fail("posix which unexpectedly saw the .cmd shim")
        if not rec["disagree"] or not str(rec["win_get_command"] or "").endswith(
            "mystery-tool.cmd"
        ):
            return fail("Get-Command analogue did not record the .cmd shim disagreement")

    unmodelled = cd.build_report(
        inject={
            "shell": "cmd.exe",
            "shell_version": "injected",
            "client_name": "cursor",
            "client_version": "2026.08.11",
            "os_name": "windows",
            "os_build": "probe2",
            "interpreter_versions": {
                "python3": "3.12.3",
                "node": "24.5.0",
                "bash": "5.2.21",
                "pwsh": "7.4.0",
            },
        }
    )
    print(
        f"unmodelled_cmd verdict={unmodelled['verdict']} "
        f"shell={unmodelled['cell']['shell']['name']} "
        f"remediation_len={len(unmodelled['remediation'])}"
    )
    if unmodelled["verdict"] != "UNMODELLED":
        return fail("cmd.exe was not UNMODELLED")
    if unmodelled["cell"]["shell"]["name"] != "cmd.exe":
        return fail("cmd.exe was collapsed onto another shell")
    if not str(unmodelled["remediation"]).strip():
        return fail("unmodelled cmd.exe produced empty remediation")

    attempts = cd.live_cross_shell_attempts()
    by_shell = {a["shell"]: a for a in attempts["attempts"]}
    print(
        "cross_shell "
        + " ".join(
            f"{k}=present:{v.get('present')} rc={v.get('exit_code')}"
            for k, v in by_shell.items()
        )
    )
    if "pwsh7" not in by_shell:
        return fail("pwsh7 attempt missing from cross-shell record")
    if by_shell["pwsh7"].get("present") is True and by_shell["pwsh7"].get("exit_code") == 0:
        print("pwsh7_live=ran")
    else:
        if by_shell["pwsh7"].get("present") is not False and by_shell["pwsh7"].get("exit_code") != 127:
            # Still a named reading; FileNotFound is the expected Linux case.
            print(f"pwsh7_named_missing={by_shell['pwsh7']}")
        if by_shell["pwsh7"].get("present") is False:
            print("pwsh7_live=MISSING-RECORDED")
        else:
            print("pwsh7_live=named-non-zero")
    if "git-bash" not in by_shell:
        return fail("git-bash attempt missing from cross-shell record")
    if by_shell["git-bash"].get("present") is False:
        print("git-bash_live=MISSING-RECORDED")

    if not RECEIPT.is_file():
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared {st}")
    if "SUCCESS:IMP-0046" not in text:
        return fail("sentinel absent")
    if doc.get("compatibility_report", {}).get("measured_from_shell", {}).get("name") not in {
        "bash",
        "sh",
        "zsh",
        "pwsh7",
        "git-bash",
        "wsl-bash",
    }:
        return fail("receipt live cell did not name a modelled shell")
    print("SUCCESS:IMP-0046-probe2 live cell, disagreement, unmodelled cmd.exe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
