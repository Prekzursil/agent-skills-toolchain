#!/usr/bin/env python3
"""Live IMP-0461 scenario: both-shell resolve, CRLF control, bare refusal."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LAUNCHER = REPO / "tools" / "launcher"
sys.path.insert(0, str(LAUNCHER))

import explicit_interpreter as ei  # noqa: E402

ESTATE = HERE / "fixtures" / "estate"
MSYS_DIR = ESTATE / "Git" / "usr" / "bin"
SYS_DIR = ESTATE / "Windows" / "System32"
SCRIPTS = HERE / "fixtures" / "scripts"


def shells() -> dict[str, list[str]]:
    MSYS_DIR.joinpath("bash").chmod(0o755)
    SYS_DIR.joinpath("bash").chmod(0o755)
    return {
        "msys": [str(MSYS_DIR.resolve())],
        "system": [str(SYS_DIR.resolve())],
    }


def write_scripts() -> dict[str, str]:
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    lf = SCRIPTS / "lf-ok.sh"
    crlf = SCRIPTS / "crlf.sh"
    lf.write_bytes(b"#!/bin/bash\necho IMP0461_LF_OK\n")
    crlf.write_bytes(b"#!/bin/bash\r\ntrue\r\n")
    lf.chmod(0o755)
    crlf.chmod(0o755)
    return {"lf": str(lf), "crlf": str(crlf)}


def independent_dir_walk(shells_map: dict[str, list[str]]) -> dict[str, str]:
    """Probe-2 style census: listdir each PATH dir; do not call resolve_name."""
    found: dict[str, str] = {}
    for shell_id, dirs in shells_map.items():
        for d in dirs:
            p = Path(d)
            if not p.is_dir():
                continue
            for name in ("bash", "bash.exe"):
                hit = p / name
                if hit.is_file():
                    found[shell_id] = str(hit.resolve())
                    break
    return found


def run_scenario() -> dict:
    sh = shells()
    scripts = write_scripts()
    table = ei.resolve_name("bash", sh)
    control = ei.wrong_bash_if_single_path("bash", sh)
    walk = independent_dir_walk(sh)
    crlf = Path(scripts["crlf"])
    lf = Path(scripts["lf"])
    strict = ei.launch(crlf, interpreter="bash", family="wsl-system", shells=sh)
    tolerant = ei.launch(crlf, interpreter="bash", family="msys", shells=sh)
    lf_strict = ei.launch(lf, interpreter="bash", family="wsl-system", shells=sh)
    lf_msys = ei.launch(lf, interpreter="bash", family="msys", shells=sh)
    bare_error = ""
    bare_refused = False
    try:
        ei.argv_for(lf)
    except ei.BareInvocationRefused as exc:
        bare_refused = True
        bare_error = str(exc)
    family_required = False
    try:
        ei.argv_for(lf, interpreter="bash", shells=sh)
    except ei.AmbiguousInterpreter:
        family_required = True
    msys_path = table.path_for_shell("msys") or ""
    sys_path = table.path_for_shell("system") or ""
    return {
        "ok": (
            table.shells_disagree
            and table.both_consulted
            and ei.classify_bash(msys_path) == "msys"
            and ei.classify_bash(sys_path) == "wsl-system"
            and control["first_wins_hides_the_other"]
            and strict.returncode != 0
            and tolerant.returncode == 0
            and lf_strict.returncode == 0
            and lf_msys.returncode == 0
            and bare_refused
            and family_required
            and walk.get("msys") == msys_path
            and walk.get("system") == sys_path
        ),
        "table": table.as_dict(),
        "msys_path": msys_path,
        "system_path": sys_path,
        "msys_family": ei.classify_bash(msys_path),
        "system_family": ei.classify_bash(sys_path),
        "independent_walk": walk,
        "first_wins_control": control,
        "first_wins_control": control,
        "crlf_strict_rc": strict.returncode,
        "crlf_strict_stderr": (strict.stderr or "")[-500:],
        "crlf_tolerant_rc": tolerant.returncode,
        "crlf_strict_rc": strict.returncode,
        "crlf_tolerant_rc": tolerant.returncode,
        "lf_strict_rc": lf_strict.returncode,
        "lf_msys_rc": lf_msys.returncode,
        "bare_refused": bare_refused,
        "bare_error": bare_error,
        "bare_error": bare_error,
        "family_required_when_disagree": family_required,
        "scripts": scripts,
        "shells": sh,
    }


def main() -> int:
    result = run_scenario()
    printable = {k: result[k] for k in result if k != "table"}
    printable["rows"] = result["table"]["rows"]
    print(json.dumps(printable, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0461-scenario" if result["ok"] else "FAILED:IMP-0461-scenario")
    return 0 if result["ok"] else 1


run_scenario = run_scenario


if __name__ == "__main__":
    raise SystemExit(main())
