#!/usr/bin/env python3
"""Probe 2: reviewer injection the implementer did not use as the catalog filename.

Implementer token is `'`, `"`, `$(id)`, space. This probe uses backticks,
semicolon, and `$HOME` through the same argv-array entrypoints, plus the
negative-control concatenated spawn which must still corrupt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
GUARD = REPO / "tools" / "glob-argv-guard"
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0019.json"
sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(GUARD))

import argv_only as ao  # noqa: E402
import glob_argv_guard as gag  # noqa: E402
from exit_codes import observe_argv  # noqa: E402

NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
INJECTION = gag.REVIEWER_INJECTION


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0019-probe2 {msg}")
    return 1


def main() -> int:
    print(f"reviewer_injection={INJECTION!r}")
    if INJECTION == gag.HOSTILE_FILENAME:
        return fail("reviewer token equals implementer token")
    if "`" not in INJECTION or ";" not in INJECTION:
        return fail("reviewer token missing backtick or semicolon")

    got = ao.echo_argv(INJECTION)
    print(f"spawn_echo={got!r}")
    if got != [INJECTION]:
        return fail(f"spawn did not round-trip: {got!r}")

    wrapped = ao.wrap_argv_for_shell(
        "bash", [sys.executable, "-B", str(gag.ECHO_CHILD), INJECTION]
    )
    if INJECTION in wrapped[2]:
        return fail("injection interpolated into bash -c string")
    proc_out = ao.spawn(wrapped, capture_output=True, text=True, timeout=20)
    if proc_out.returncode != 0:
        return fail(f"bash wrap rc={proc_out.returncode} {proc_out.stderr}")
    echoed = ao.parse_echo(proc_out.stdout)
    print(f"bash_wrap_echo={echoed!r}")
    if echoed != [INJECTION]:
        return fail(f"bash wrap corrupted: {echoed!r}")

    observed = observe_argv(
        [sys.executable, "-B", str(gag.ECHO_CHILD), INJECTION], via="bash"
    )
    print(f"observe_argv present={observed.present} rc={observed.exit_code}")
    if not observed.present or observed.exit_code != 0:
        return fail(f"observe_argv {observed.error or observed.stderr}")
    if ao.parse_echo(observed.stdout) != [INJECTION]:
        return fail("observe_argv corrupted reviewer injection")

    import importlib.util

    fixture = GUARD / "fixtures" / "concatenated_spawn.py"
    spec = importlib.util.spec_from_file_location("concatenated_spawn", fixture)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mutant = mod.run_concatenated(sys.executable, str(gag.ECHO_CHILD), INJECTION)
    received = None
    if (mutant.stdout or "").strip():
        try:
            received = json.loads(mutant.stdout.strip().splitlines()[-1]).get("argv")
        except json.JSONDecodeError:
            received = None
    print(f"concatenated_received={received!r}")
    if received == [INJECTION]:
        return fail("concatenated spawn preserved reviewer injection")

    if not RECEIPT.is_file():
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared {st}")
    if "SUCCESS:IMP-0019" not in text:
        return fail("sentinel absent")
    print("SUCCESS:IMP-0019-probe2 reviewer backtick/semicolon injection plus concat control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
