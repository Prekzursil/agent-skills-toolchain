"""Both directions under ONE scoped configuration (IMP-0466).

The revision survives unconverted AND the legitimate POSIX path converts with
the clone marker present. A run showing only one direction is half a proof.
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
    report = pc.both_directions_report()
    scoped = report["scoped"]
    conv = report["conversion_on"]

    assert report["pass"] is True, report
    assert report["same_configuration"] is True
    assert scoped["revision_unconverted"] is True, scoped
    assert scoped["revision_observed"] == "/refs/heads/main"
    assert scoped["device_unconverted"] is True, scoped
    assert scoped["posix_converted"] is True, scoped
    assert scoped["posix_observed"].endswith("repo")
    assert scoped["clone_intended_exists"] is True
    # the conversion-on control shows the raw MSYS behavior the scope prevents
    assert conv["revision_corrupted"] is True, conv
    assert conv["device_observed"] == "NUL", conv
    assert conv["posix_converted"] is True, conv

    matrix = pc.per_argument_shape_matrix("scoped")
    by_id = {row["id"]: row for row in matrix}
    assert by_id["rev-refs"]["observed"] == "/refs/heads/main"
    assert by_id["dev-null"]["observed"] == "/dev/null"
    assert by_id["dev-null"]["converted"] is False
    assert by_id["posix-clone-dest"]["observed"].endswith("repo")

    print(json.dumps({
        "probe": "probe1-both-directions",
        "unit_id": "IMP-0466",
        "pass": report["pass"],
        "same_configuration": report["same_configuration"],
        "revision_observed_scoped": scoped["revision_observed"],
        "revision_unconverted": scoped["revision_unconverted"],
        "device_unconverted": scoped["device_unconverted"],
        "posix_original": "/c/Users/probe/repo",
        "posix_observed_scoped": scoped["posix_observed"],
        "clone_marker_exists": scoped["clone_intended_exists"],
        "sentinel": "SENTINEL:IMP-0466:PATHCONV-ARGUMENT-SCOPED",
    }, indent=2))
    print("SUCCESS:IMP-0466-probe1 revision survives unconverted AND posix converts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
