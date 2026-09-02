#!/usr/bin/env python3
"""Probe 1: two-shell availability + negative control + .cmd both-states.

Mechanically different from probe 2 (which censuses frozen source/docs).
Settling signals are Get-Command (live pwsh if present, else PATHEXT analogue)
AND an invocation. Git Bash which is reported, never used as absence proof.
"""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import NOT_DELIVERING, OUT_REL, SENTINEL, UNIT  # noqa: E402
from detector import (  # noqa: E402
    ABSENT_BIN,
    TARGET,
    auth_state,
    dual_resolve,
    negative_control,
    two_shell_availability,
)

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def check_artifact(avail: dict, neg: dict) -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "artifact-missing"
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return f"self-declared:{st}"
    if SENTINEL not in text:
        return "sentinel-absent"
    if "two-shell availability verdict" not in text:
        return "verdict-phrase-absent"
    answers = doc.get("answers") or {}
    if answers.get("two_shell_availability_verdict") != avail["two_shell_availability_verdict"]:
        return (
            f"verdict-mismatch live={avail['two_shell_availability_verdict']} "
            f"art={answers.get('two_shell_availability_verdict')}"
        )
    if answers.get("settled_available") != avail["settled_available"]:
        return "settled-mismatch"
    if answers.get("fallback_required") is not True and not avail["settled_available"]:
        return "fallback-not-required-on-miss"
    if answers.get("negative_control_said_no") is not True:
        return "negative-control-not-recorded"
    if answers.get("version_from_invocation") != avail["version_from_invocation"]:
        return "version-mismatch"
    tv = doc.get("two_shell_availability_verdict") or {}
    if "powershell_get_command" not in tv or "git_bash" not in tv:
        return "two-shell-columns-missing"
    if ABSENT_BIN not in text:
        return "absent-bin-not-named"
    if neg["detector_said_no"] is not True:
        return "live-negative-control-failed"
    return None


def cmd_shim_both_states() -> str | None:
    with tempfile.TemporaryDirectory() as td:
        shim = Path(td) / f"{TARGET}-planted.cmd"
        shim.write_text("@echo off\r\n", encoding="utf-8")
        os.chmod(shim, stat.S_IRUSR | stat.S_IWUSR)
        rec = dual_resolve(f"{TARGET}-planted", [td])
        print(
            f"cmd_shim posix={rec['posix_which']!r} "
            f"get_command={rec['win_get_command']!r} disagree={rec['disagree']}"
        )
        if rec["posix_which"] is not None:
            return "posix-which-saw-cmd-shim"
        win = str(rec.get("win_get_command") or "")
        if not rec["disagree"] or not win.endswith(".cmd"):
            return "get-command-analogue-missed-cmd-shim"
    return None


def main() -> int:
    avail = two_shell_availability()
    neg = negative_control()
    auth = auth_state()
    print(
        "target={t} verdict={v} settled={s} fallback={f} version={ver!r} "
        "pwsh_present={p} git_bash_present={g} invoke_ran={r} invoke_rc={rc} "
        "invoke_err={e} analogue={a!r}".format(
            t=avail["target"],
            v=avail["two_shell_availability_verdict"],
            s=avail["settled_available"],
            f=avail["fallback_required"],
            ver=avail["version_from_invocation"],
            p=avail["powershell_get_command"]["shell_present"],
            g=avail["git_bash"]["shell_present"],
            r=avail["invocation"]["ran"],
            rc=avail["invocation"]["exit_code"],
            e=avail["invocation"]["error"],
            a=avail["get_command_analogue"]["win_get_command"],
        )
    )
    print(
        f"negative_control tool={neg['tool']} said_no={neg['detector_said_no']} "
        f"auth={auth['authenticated']}"
    )
    if not neg["detector_said_no"]:
        return fail("negative control did not say no")
    if avail["posix_command_v_non_settling"] and not avail["get_command_analogue"]["win_get_command"]:
        return fail("posix command -v hit without Get-Command analogue; record disagreement")
    # Settling: both signals must agree on the boolean used for assignment.
    get_hit = bool(
        avail["powershell_get_command"].get("resolved")
        or avail["get_command_analogue"].get("win_get_command")
    )
    inv_ok = bool(avail["invocation"].get("ran") and avail["invocation"].get("exit_code") == 0)
    if avail["settled_available"] != (get_hit and inv_ok):
        return fail("settled_available is not the conjunction of Get-Command and invocation")
    if avail["fallback_required"] != (not avail["settled_available"]):
        return fail("fallback_required disagrees with settled_available")
    shim_err = cmd_shim_both_states()
    if shim_err:
        return fail(shim_err)
    art_err = check_artifact(avail, neg)
    if art_err:
        return fail(f"artifact {art_err}")
    print(
        f"SUCCESS:{UNIT}-probe1 two-shell availability verdict="
        f"{avail['two_shell_availability_verdict']} negative_control=no"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
