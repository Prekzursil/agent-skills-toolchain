#!/usr/bin/env python3
"""IMP-0192 probe 2: zero false positives on the admitted library (computed)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOLS = REPO / "tools"
TESTS = TOOLS / "agentrail" / "tests"
sys.path.insert(0, str(TOOLS / "agentspec"))
sys.path.insert(0, str(TOOLS / "agentrail"))
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TESTS))

from test_no_rival_core import test_admitted_library_silent  # noqa: E402
from workflow_foundry.control_plane import (  # noqa: E402
    scan_generated_artifacts,
    scan_library,
)


def main() -> int:
    silent = test_admitted_library_silent()
    library = scan_library(REPO)
    generated = scan_generated_artifacts(REPO)
    # Set difference of findings vs empty set, computed — not asserted in prose.
    finding_ids = {
        (row["path"], row["plane"], row["name"], row["kind"])
        for row in library["findings"]
    }
    empty: set[tuple[str, str, str, str]] = set()
    delta = sorted(finding_ids - empty)
    ok = (
        bool(silent["pass"])
        and int(library["files_scanned"]) >= 6
        and int(library["finding_count"]) == 0
        and int(generated["finding_count"]) == 0
        and delta == []
    )
    payload = {
        "id": "library-zero-false-positives",
        "pass": ok,
        "library_files_scanned": library["files_scanned"],
        "library_finding_count": library["finding_count"],
        "library_by_plane": library["by_plane"],
        "generated_files_scanned": generated["files_scanned"],
        "generated_finding_count": generated["finding_count"],
        "set_difference_vs_empty": delta,
        "files": silent["files"],
        "silent_test": silent,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0192-probe2 library false positives")
        return 1
    print(
        "SUCCESS:IMP-0192-probe2 zero false positives across "
        f"{library['files_scanned']} admitted artifacts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
