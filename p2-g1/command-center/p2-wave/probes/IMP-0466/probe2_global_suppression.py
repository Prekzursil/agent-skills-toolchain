"""Adversarial refuter: global suppression is NOT equivalent to the scoped control (IMP-0466).

A global MSYS_NO_PATHCONV fixture must FAIL the legitimate-path direction
(silent no-op clone + truncated redirect) while the scoped control passes it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

import shell.pathconv as pc  # noqa: E402


def main() -> int:
    report = pc.global_suppression_discrimination_report()
    scoped = report["scoped"]
    glob = report["global"]

    assert report["pass"] is True, report
    assert report["discriminates"] is True
    assert report["revision_survives_both"] is True, "revision must survive under both"
    assert scoped["posix_converted"] and scoped["clone_happened"]
    assert scoped["redirect_ok"] is True
    assert (not glob["posix_converted"]), "global suppression breaks the path direction"
    assert glob["silent_noop"] is True
    assert (not glob["clone_intended_exists"]), "clone silently no-oped under global"
    assert glob["redirect_truncated"] is True and glob["redirect_content"] == ""

    print(json.dumps({
        "probe": "probe2-global-suppression",
        "unit_id": "IMP-0466",
        "pass": report["pass"],
        "discriminates": report["discriminates"],
        "revision_survives_both": report["revision_survives_both"],
        "scoped_posix_converted": scoped["posix_converted"],
        "scoped_clone_happened": scoped["clone_happened"],
        "global_posix_converted": glob["posix_converted"],
        "global_silent_noop_clone": glob["silent_noop"],
        "global_redirect_truncated": glob["redirect_truncated"],
        "adversarial_refuter": "silent-noop clone direction (global fixture)",
        "sentinel": "SENTINEL:IMP-0466:PATHCONV-ARGUMENT-SCOPED",
    }, indent=2))
    print("SUCCESS:IMP-0466-probe2 global suppression fails the legit path; scoped passes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
