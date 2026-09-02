#!/usr/bin/env python3
"""Probe 2: live POSIX $? vs PowerShell $LASTEXITCODE, plus negative control.

Mechanically different from probe 1 (which runs the unittest file). This probe
re-spawns the CLI through bash -lc '...; exit $?' and through pwsh
`exit $LASTEXITCODE`, and asserts a failing check that printed a report never
returns 0.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from plugin.exit_codes import (  # noqa: E402
    BLOCKED_NEEDS_OWNER,
    INTERNAL_ERROR,
    PERMISSION_DENIED,
    PRECONDITION_FAILED,
    SUCCESS,
    USAGE_ERROR,
    VALIDATION_FAILED,
    cli_argv,
    is_shell_reserved,
    names,
    observe_argv,
)

RECEIPT = REPO / "command-center/receipts/IMP-0055.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
PERM_DENIED_PATH = "/sys/imp0055-denied"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0055-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0055-p2-") as td:
        bad = Path(td) / "bad.json"
        bad.write_text("{}", encoding="utf-8")
        missing = Path(td) / "no-such.json"
        cases = {
            "success": (cli_argv("verify"), SUCCESS),
            "usage_error": (cli_argv("not-a-verb"), USAGE_ERROR),
            "precondition_failed": (
                cli_argv("preflight", "--require-file", str(missing)),
                PRECONDITION_FAILED,
            ),
            "validation_failed": (
                cli_argv("check", "--file", str(bad)),
                VALIDATION_FAILED,
            ),
            "permission_denied": (
                cli_argv("write", "--path", PERM_DENIED_PATH, "--body", "x"),
                PERMISSION_DENIED,
            ),
            "blocked_needs_owner": (
                cli_argv(
                    "owner-gate",
                    "--installed",
                    "fs:read",
                    "--candidate",
                    "fs:read",
                    "--candidate",
                    "net:connect",
                ),
                BLOCKED_NEEDS_OWNER,
            ),
            "internal_error": (cli_argv("internal"), INTERNAL_ERROR),
        }

        rows = []
        pwsh_any_present = False
        for name, (argv, expected) in cases.items():
            native = observe_argv(argv, via="native")
            bash = observe_argv(argv, via="bash")
            pwsh = observe_argv(argv, via="pwsh7")
            if pwsh.present:
                pwsh_any_present = True
            row = {
                "case": name,
                "expected": expected,
                "native": native.exit_code,
                "bash_posix_status": bash.exit_code,
                "pwsh_lastexitcode": pwsh.exit_code if pwsh.present else None,
                "pwsh_present": pwsh.present,
                "pwsh_error": pwsh.error,
                "bash_present": bash.present,
            }
            rows.append(row)
            print(
                f"{name} expected={expected} native={native.exit_code} "
                f"bash={bash.exit_code} pwsh_present={pwsh.present} "
                f"pwsh={pwsh.exit_code}"
            )
            if native.exit_code != expected:
                return fail(f"{name} native {native.exit_code} != {expected}")
            if not bash.present or bash.exit_code != expected:
                return fail(f"{name} bash $? {bash.exit_code} != {expected}")
            if bash.exit_code != native.exit_code:
                return fail(f"{name} bash $? did not survive the POSIX shell boundary")
            if pwsh.present and pwsh.exit_code != expected:
                return fail(
                    f"{name} pwsh $LASTEXITCODE {pwsh.exit_code} != {expected}"
                )
            if name != "success" and native.exit_code == 0:
                return fail(f"{name} leaked exit 0")
            if is_shell_reserved(expected):
                return fail(f"{name} expected code {expected} is shell-reserved")

        # NEGATIVE CONTROL: printed report + finished:true must not be exit 0.
        neg_native = observe_argv(cases["validation_failed"][0], via="native")
        neg_bash = observe_argv(cases["validation_failed"][0], via="bash")
        try:
            neg_doc = json.loads(neg_native.stdout or "")
        except json.JSONDecodeError as exc:
            return fail(f"negative-control stdout is not JSON: {exc}")
        print(
            f"negative_control finished={neg_doc.get('finished')} "
            f"ok={neg_doc.get('ok')} bash={neg_bash.exit_code} "
            f"native={neg_native.exit_code} stdout_bytes={len(neg_native.stdout or '')}"
        )
        if neg_doc.get("finished") is not True:
            return fail("negative-control report missing finished=true")
        if neg_doc.get("ok") is not False:
            return fail("negative-control report claimed ok")
        if not (neg_native.stdout or "").strip():
            return fail("negative-control printed no report")
        if neg_native.exit_code == 0 or neg_bash.exit_code == 0:
            return fail("negative-control exited 0 after printing a report")
        if neg_native.exit_code != VALIDATION_FAILED:
            return fail("negative-control was not VALIDATION_FAILED")

        if not pwsh_any_present:
            print("pwsh7_live=MISSING-RECORDED")
        else:
            print("pwsh7_live=ran")

        for code, label in names().items():
            if is_shell_reserved(code):
                return fail(f"{label}={code} collides with 126/127/128+n")
        print("reviewer_shell_reserved=PASS none of", list(names().items()), "in 126/127/128+n")

        if not RECEIPT.is_file():
            return fail("receipt missing")
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            return fail(f"self-declared {st}")
        if "SUCCESS:IMP-0055" not in text:
            return fail("sentinel absent")

        payload = {
            "probe": "probe2-cross-shell",
            "unit_id": "IMP-0055",
            "rows": rows,
            "pwsh7_present": pwsh_any_present,
            "negative_control": {
                "finished": neg_doc.get("finished"),
                "ok": neg_doc.get("ok"),
                "exit_code": neg_native.exit_code,
                "bash_exit_code": neg_bash.exit_code,
            },
        }
        print(json.dumps(payload, sort_keys=True, default=str)[:4000])
        print("SUCCESS:IMP-0055-probe2 posix $?, pwsh $LASTEXITCODE wrap, negative control")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
