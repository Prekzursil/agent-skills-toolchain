#!/usr/bin/env python3
"""Probe 2: independent PATH walk + CRLF under the real (strict) interpreter.

Does not call resolve_name for the census. Re-walks each shell PATH directory
and requires the launcher table to match. CRLF must fail under wsl-system
(the real target) and succeed under the tolerant MSYS wrapper.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LAUNCHER = REPO / "tools" / "launcher"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAUNCHER))
import explicit_interpreter as ei  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0461.json"
SENTINEL = "SENTINEL:IMP-0461:INTERPRETER-EXPLICIT"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    run = S.run_scenario()
    reversed_shells = {
        "system": run["shells"]["system"],
        "msys": run["shells"]["msys"],
    }
    reresolve = ei.resolve_name("bash", reversed_shells)
    walk = run["independent_walk"]
    out = {
        "walk_msys": walk.get("msys"),
        "walk_system": walk.get("system"),
        "table_msys": run["msys_path"],
        "table_system": run["system_path"],
        "reresolve_msys": reresolve.path_for_shell("msys"),
        "reresolve_system": reresolve.path_for_shell("system"),
        "crlf_strict_rc": run["crlf_strict_rc"],
        "crlf_tolerant_rc": run["crlf_tolerant_rc"],
        "bare_refused": run["bare_refused"],
        "walk_matches_table": (
            walk.get("msys") == run["msys_path"]
            and walk.get("system") == run["system_path"]
        ),
        "other_shell_first_agrees": (
            reresolve.path_for_shell("msys") == run["msys_path"]
            and reresolve.path_for_shell("system") == run["system_path"]
        ),
    }
    print(json.dumps(out, sort_keys=True))
    if not out["walk_matches_table"]:
        print("FAILED:IMP-0461-probe2 independent walk != launcher table")
        return 1
    if not out["other_shell_first_agrees"]:
        print("FAILED:IMP-0461-probe2 re-resolve from the other shell disagreed")
        return 1
    if run["crlf_strict_rc"] == 0:
        print("FAILED:IMP-0461-probe2 CRLF passed under the strict interpreter")
        return 1
    if run["crlf_tolerant_rc"] != 0:
        print("FAILED:IMP-0461-probe2 CRLF failed under the tolerant MSYS wrapper")
        return 1
    if run["crlf_strict_rc"] == run["crlf_tolerant_rc"]:
        print("FAILED:IMP-0461-probe2 CRLF detector silent in both states")
        return 1
    if not run["bare_refused"]:
        print("FAILED:IMP-0461-probe2 bare invocation was not refused")
        return 1
    if not ART.is_file():
        print("FAILED:IMP-0461-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:IMP-0461-probe2 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:IMP-0461-probe2 sentinel-absent")
        return 1
    meas = doc.get("measurement") or {}
    strict_rc = meas.get("crlf_strict_rc")
    tolerant_rc = meas.get("crlf_tolerant_rc")
    if strict_rc is None or int(strict_rc) == 0:
        print("FAILED:IMP-0461-probe2 receipt claims CRLF strict passed")
        return 1
    if tolerant_rc is None or int(tolerant_rc) != 0:
        print("FAILED:IMP-0461-probe2 receipt claims CRLF tolerant failed")
        return 1
    if meas.get("bare_refused") is not True:
        print("FAILED:IMP-0461-probe2 receipt did not record bare_refused")
        return 1
    print(
        f"walk_match={out['walk_matches_table']} "
        f"crlf_strict={run['crlf_strict_rc']} crlf_msys={run['crlf_tolerant_rc']}"
    )
    print("SUCCESS:IMP-0461-probe2 independent walk and CRLF detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
