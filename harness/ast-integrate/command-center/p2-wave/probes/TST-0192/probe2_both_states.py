#!/usr/bin/env python3
"""Probe 2: both-states real-bash vs Git-Bash analogue (signal b).

Mechanically different from probe 1: plants a CRLF fixture and runs two
syntax checkers. Does not trust receipt both_states booleans; re-runs them.
A Git-Bash-only checker would green the CRLF plant — that is the control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from detectors import (  # noqa: E402
    both_states,
    inventory_sh,
    real_bash_n,
    receipt_shell_fields,
)
from emitter import emit  # noqa: E402

ART = REPO / "command-center/receipts/TST-0192.json"
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:TST-0192-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0192" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in BLOCKED:
        return fail(f"self-declared {doc.get('state')}")

    emit()
    ctl = both_states()
    if not ctl["crlf_real_bash_fails"]:
        return fail("CRLF fixture did not fail real bash -n")
    if not ctl["crlf_git_bash_passes"]:
        return fail("CRLF fixture did not pass Git-Bash analogue (detectors identical)")
    if not ctl["lf_real_bash_passes"]:
        return fail("LF fixture failed real bash -n")
    if not ctl["detectors_differ"]:
        return fail("detectors do not differ")
    if not ctl["git_bash_not_vacuous"]:
        return fail("Git-Bash analogue is vacuous (accepts broken syntax)")

    rec = receipt_shell_fields(doc)["both_states"]
    for key in (
        "crlf_real_bash_fails",
        "crlf_git_bash_passes",
        "lf_real_bash_passes",
        "detectors_differ",
    ):
        if rec.get(key) is not True:
            return fail(f"receipt both_states.{key} is not true")

    for path in inventory_sh():
        bn = real_bash_n(path)
        if bn["exit"] != 0:
            return fail(f"emitted {path.name} real-bash -n exit={bn['exit']}")

    out = {
        "probe": "probe2-both-states",
        "unit_id": "TST-0192",
        "crlf_real_exit": ctl["crlf_real"]["exit"],
        "crlf_git_exit": ctl["crlf_git"]["exit"],
        "lf_real_exit": ctl["lf_real"]["exit"],
        "broken_real_exit": ctl["broken_real"]["exit"],
        "broken_git_exit": ctl["broken_git"]["exit"],
        "detectors_differ": True,
        "regression_seed": ctl["regression_seed"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:TST-0192-probe2 CRLF fails real bash, passes Git-Bash analogue")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
