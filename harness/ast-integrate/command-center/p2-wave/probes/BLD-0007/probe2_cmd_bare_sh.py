#!/usr/bin/env python3
"""Probe 2: cmd.exe bare-.sh catch, no-assertion validator, dash reviewer.

1. cmd.exe cell probe must catch `bare .sh invocation on Windows`.
2. A probe that emits no assertion must fail the matrix validator.
3. Independent reviewer re-runs two emitted probes from /bin/sh (dash),
   a shell the author did not use, and reports any silent PASS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from cmd_model import FAILURE_CLASS, catch_bare_sh  # noqa: E402
from reviewer import reviewer_dash  # noqa: E402
from validator import get_cells, validate_probe_source, validate_receipt_file  # noqa: E402

OUT = REPO / "command-center/receipts/BLD-0007.json"
CMD_PROBE = "command-center/p2-wave/probes/BLD-0007/cells/windows__cmd.exe.py"


def main() -> int:
    if not OUT.is_file():
        print("FAILED:BLD-0007-probe2 receipt absent")
        return 1
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0007-probe2 self-declared:{doc.get('state')}")
        return 1
    errs = validate_receipt_file(OUT, REPO)
    if errs:
        print("FAILED:BLD-0007-probe2 validator", errs[:12])
        return 1

    caught = catch_bare_sh()
    print(
        f"bare_sh caught={caught['ok']} class={caught['bare']['failure_class']} "
        f"ext_in_pathext={caught['bare']['extension_in_pathext']} "
        f"shebang={caught['bare']['shebang_honored']}"
    )
    if not caught["ok"]:
        print("FAILED:BLD-0007-probe2 cmd.exe probe did not catch bare .sh")
        return 1
    if caught["bare"]["failure_class"] != FAILURE_CLASS:
        print("FAILED:BLD-0007-probe2 wrong failure class")
        return 1
    cmd_cell = next(
        (c for c in (get_cells(doc) or []) if c.get("id") == "windows__cmd.exe"),
        None,
    )
    if cmd_cell is None:
        print("FAILED:BLD-0007-probe2 cmd.exe cell missing")
        return 1
    if str(cmd_cell.get("probe_path") or "").replace("\\", "/") != CMD_PROBE:
        print(f"FAILED:BLD-0007-probe2 probe_path {cmd_cell.get('probe_path')}")
        return 1
    if cmd_cell.get("status") == "PASS":
        print("FAILED:BLD-0007-probe2 cmd.exe cell PASS")
        return 1
    if not cmd_cell.get("bare_sh_control", {}).get("ok"):
        print("FAILED:BLD-0007-probe2 receipt missing bare_sh catch")
        return 1

    no_assert = HERE / "fixtures" / "no_assertion.py"
    if not no_assert.is_file():
        no_assert.parent.mkdir(parents=True, exist_ok=True)
        no_assert.write_text('print("ok")\n', encoding="utf-8")
    na_errs = validate_probe_source(no_assert)
    print(f"no_assertion errors={na_errs}")
    if not na_errs:
        print("FAILED:BLD-0007-probe2 validator accepted no-assertion probe")
        return 1
    live_probe_errs = validate_probe_source(REPO / CMD_PROBE)
    if live_probe_errs:
        print("FAILED:BLD-0007-probe2 live cmd probe failed assertion scan", live_probe_errs)
        return 1

    by_id = {c["id"]: c for c in (get_cells(doc) or []) if isinstance(c, dict)}
    review = reviewer_dash(
        [by_id["linux__posix-sh"]["probe_path"], by_id["linux__powershell-7"]["probe_path"]]
    )
    print(
        f"reviewer shell={review['reviewer_shell_target']} "
        f"silent_pass={review['silent_pass']} verdict={review['verdict']} "
        f"rcs={[r['rc'] for r in review['probes_run']]}"
    )
    if review["silent_pass"] or review["verdict"] != "PASS":
        print("FAILED:BLD-0007-probe2 silent pass under reviewer shell")
        return 1
    if any(r["rc"] != 0 for r in review["probes_run"]):
        print("FAILED:BLD-0007-probe2 reviewer probe rc")
        return 1
    rec_rev = doc.get("reviewer") or {}
    if rec_rev.get("independent") is not True:
        print("FAILED:BLD-0007-probe2 reviewer not independent")
        return 1

    print("SUCCESS:BLD-0007-probe2 cmd-bare-sh validator reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
