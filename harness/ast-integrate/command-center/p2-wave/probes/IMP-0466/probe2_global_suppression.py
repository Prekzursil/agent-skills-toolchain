#!/usr/bin/env python3
"""Probe 2: global-suppression fixture fails the legitimate-path case.

Adversarial refuter on the silent-no-op direction. Scoped clone must create
the intended Windows path; global MSYS_NO_PATHCONV must not. Redirect under
global suppression must truncate the intended target. If global also converts
the POSIX path, this probe cannot discriminate and must FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.shell.pathconv import (  # noqa: E402
    FAILURE_GLOBAL_SUPPRESSION,
    FAILURE_REDIRECT_TRUNCATION,
    FAILURE_SILENT_NOOP_CLONE,
    global_suppression_discrimination_report,
)

UID = "IMP-0466"


def main() -> int:
    report = global_suppression_discrimination_report()
    scoped = report["scoped"]
    glob = report["global"]
    payload = {
        "probe": "probe2-global-suppression",
        "unit_id": UID,
        "pass": report["pass"],
        "discriminates": report["discriminates"],
        "revision_survives_both": report["revision_survives_both"],
        "note": report["note"],
        "scoped_posix_converted": scoped["posix_converted"],
        "scoped_clone_happened": scoped["clone_happened"],
        "scoped_clone_intended_exists": scoped["clone_intended_exists"],
        "scoped_redirect_ok": scoped["redirect_ok"],
        "scoped_redirect_content": scoped["redirect_content"],
        "scoped_global_flag": scoped["global_suppression"],
        "global_posix_converted": glob["posix_converted"],
        "global_silent_noop": glob["silent_noop"],
        "global_clone_intended_exists": glob["clone_intended_exists"],
        "global_redirect_truncated": glob["redirect_truncated"],
        "global_redirect_content": glob["redirect_content"],
        "global_flag": glob["global_suppression"],
        "failure_classes": [
            FAILURE_GLOBAL_SUPPRESSION,
            FAILURE_SILENT_NOOP_CLONE,
            FAILURE_REDIRECT_TRUNCATION,
        ],
    }
    print(json.dumps(payload, sort_keys=True))

    if scoped["global_suppression"]:
        print("FAILED:IMP-0466-probe2 scoped mode used global suppression")
        return 1
    if not glob["global_suppression"]:
        print("FAILED:IMP-0466-probe2 global fixture did not set global suppression")
        return 1
    if glob["posix_converted"]:
        print(
            "FAILED:IMP-0466-probe2 global fixture still converted POSIX path "
            "(cannot discriminate from scoped)"
        )
        return 1
    if not scoped["posix_converted"] or not scoped["clone_happened"]:
        print("FAILED:IMP-0466-probe2 scoped clone did not land on intended path")
        return 1
    if glob["clone_intended_exists"]:
        print("FAILED:IMP-0466-probe2 global clone touched intended path (not a no-op)")
        return 1
    if not glob["silent_noop"]:
        print("FAILED:IMP-0466-probe2 global clone was not a silent no-op")
        return 1
    if not scoped["redirect_ok"] or scoped["redirect_content"] != "probe-body\n":
        print("FAILED:IMP-0466-probe2 scoped redirect did not write intended file")
        return 1
    if not glob["redirect_truncated"] or glob["redirect_content"] != "":
        print("FAILED:IMP-0466-probe2 global redirect did not truncate intended target")
        return 1
    if not report["revision_survives_both"]:
        print(
            "FAILED:IMP-0466-probe2 revision must survive both modes "
            "(that alone is not the proof)"
        )
        return 1
    if not report["discriminates"] or not report["pass"]:
        print("FAILED:IMP-0466-probe2 scoped is equivalent to global (dead fixture)")
        return 1
    print(
        "SUCCESS:IMP-0466-probe2 global suppression no-ops clone and truncates "
        "redirect; scoped is not equivalent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
