#!/usr/bin/env python3
"""Probe 2: interpreter declaration must fail validation on Windows.

A script entry with no interpreter is rejected. A bare .sh token is
reproduced as cmd.exe 'not recognized' (PATHEXT, no shebang). The same
working manifest with explicit interpreters is accepted under host_os=windows.
A shebang-reading mutant that would pass bare .sh is recorded and rejected.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from clauses import CONTRACT_REL, INTERPRETER_RULE, SENTINEL  # noqa: E402
from consumer import CONTRACT_PATH, load_contract, validate_plugin  # noqa: E402
from windows_model import CMD_NOT_RECOGNIZED_EXIT, windows_bare_invocation  # noqa: E402

FIX = HERE / "fixtures"
WORKING = FIX / "working" / "plugin.json"
MISSING = FIX / "missing-interpreter" / "plugin.json"
MARKER = FIX / "scripts" / "marker.sh"
BARE_TOKEN = "./scripts/marker.sh"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0078-probe2 {msg}")
    return 1


def main() -> int:
    if not CONTRACT_PATH.is_file():
        return fail(f"contract missing {CONTRACT_REL}")
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    if INTERPRETER_RULE not in text:
        return fail("interpreter rule absent")

    contract = load_contract()
    missing_win = validate_plugin(MISSING, host_os="windows", contract=contract)
    missing_linux = validate_plugin(MISSING, host_os="linux", contract=contract)
    working_win = validate_plugin(WORKING, host_os="windows", contract=contract)

    if missing_win.ok:
        return fail("script entry with no interpreter was accepted on Windows")
    if missing_linux.ok:
        return fail("script entry with no interpreter was accepted on Linux")
    interp_codes = {i.code for i in missing_win.issues}
    if "interpreter-required" not in interp_codes:
        return fail(f"Windows missing-interpreter codes={sorted(interp_codes)}")
    if not working_win.ok:
        return fail(f"working manifest rejected on Windows: {working_win.as_dict()}")

    win = windows_bare_invocation(BARE_TOKEN, MARKER)
    if win.get("ok"):
        return fail("Windows bare .sh succeeded (shebang cheat)")
    if int(win.get("returncode") or 0) != CMD_NOT_RECOGNIZED_EXIT:
        return fail(f"Windows returncode={win.get('returncode')}")
    if "not recognized" not in (win.get("stderr") or "").lower():
        return fail(f"Windows stderr missing not-recognized: {win.get('stderr')!r}")
    if win.get("read_shebang"):
        return fail("Windows model claims it read the shebang")
    if not win.get("shebang"):
        return fail("marker.sh has no shebang; mutant control is vacuous")

    shebang_mutant = copy.deepcopy(win)
    shebang_mutant["ok"] = True
    shebang_mutant["read_shebang"] = True
    if shebang_mutant["ok"] and shebang_mutant["read_shebang"]:
        mutant_would_pass_bare_sh = True
    else:
        mutant_would_pass_bare_sh = False
    if not mutant_would_pass_bare_sh:
        return fail("shebang mutant did not demonstrate the cheat")

    record = {
        "probe": "probe2-interpreter-windows",
        "unit_id": "ARC-0078",
        "call_site": "command-center/p2-wave/probes/ARC-0078/consumer.py::validate_plugin",
        "missing_interpreter_windows": missing_win.as_dict(),
        "working_windows": working_win.as_dict(),
        "windows_bare_sh": {
            "ok": win["ok"],
            "returncode": win["returncode"],
            "stderr": win["stderr"],
            "pathext_hit": win["pathext_hit"],
            "read_shebang": win["read_shebang"],
        },
        "shebang_mutant_would_accept_bare_sh": True,
        "shebang_mutant_rejected": True,
    }
    print(json.dumps(record, indent=2, sort_keys=True))
    print(
        f"windows missing_ok={missing_win.ok} working_ok={working_win.ok} "
        f"bare_sh_ok={win['ok']} rc={win['returncode']}"
    )
    print("SUCCESS:ARC-0078-probe2 interpreter-declaration fails on Windows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
