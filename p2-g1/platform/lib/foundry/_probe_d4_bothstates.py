"""Both-states control for the D4 gate, against the REAL pre-fix documents.

Materialises the four forged workflow docs as they exist at git HEAD (0aa6f8fa, pre-fix) via
`git cat-file -p`, then runs the SAME scanner the shipped test uses.

`git cat-file -p` and not `git archive`: archive applies export-time EOL conversion and returns
CRLF on this box, so it is the wrong bytes. The scanner parses JSON anyway, so the digest is
line-ending independent -- but the blob route is the correct habit.

Expected: FIRES on the pre-fix tree (divergent_ids non-empty, mixed_verdict_ids non-empty),
silent on the post-fix working tree. A probe silent in both states measures nothing.
"""

from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
PRE_FIX_REV = "0aa6f8fa"
FORGED_REL = "platform/workflows/forged"
DOCS = [
    "fused.cnc07-arc05.TOURNAMENT-WINNER.workflow.json",
    "fused.cnc07-arc05.workflow.json",
    "REJECTED.union.cnc07-arc05.workflow.json",
    "REJECTED.res05-drift.workflow.json",
]


def _load_scanner():
    """Import the scanner out of the shipped test module, so the control tests the REAL gate."""
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    spec = importlib.util.spec_from_file_location(
        "d4_test_mod", REPO / "platform" / "lib" / "foundry" / "test_foundry.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _summary(name: str, report: dict) -> bool:
    divergent = report["divergent_ids"]
    mixed = report["mixed_verdict_ids"]
    unmarked = report["unmarked_rejected_ids"]
    fired = bool(divergent or mixed or unmarked)
    print(f"[{name}]")
    print(f"   workflow_documents    : {report['workflow_documents']}")
    print(f"   distinct_ids          : {report['distinct_ids']}")
    print(f"   divergent_ids         : {list(divergent)}")
    print(f"   mixed_verdict_ids     : {mixed}")
    print(f"   unmarked_rejected_ids : {unmarked}")
    print(f"   GATE FIRED            : {fired}")
    return fired


def main() -> int:
    mod = _load_scanner()
    scan = mod._scan_workflow_ids

    # The control tree MUST live outside platform/workflows: writing it inside contaminates
    # the very tree the post-fix scan measures (measured: 107 docs instead of 103, and the
    # post-fix scan re-reported the pre-fix collision from the control files themselves).
    with tempfile.TemporaryDirectory(prefix="d4-prefix-control-") as tmp:
        pre = Path(tmp)
        for name in DOCS:
            blob = subprocess.run(
                ["git", "cat-file", "-p", f"{PRE_FIX_REV}:{FORGED_REL}/{name}"],
                capture_output=True,
                cwd=str(REPO),
                check=True,
            ).stdout
            (pre / name).write_bytes(blob)
        # control 1: the KNOWN-BROKEN pre-fix state. The gate MUST fire.
        broken = _summary(f"PRE-FIX  (known broken, git {PRE_FIX_REV})", scan(pre))
        print()
        # control 2: the post-fix working tree. The gate MUST be silent.
        fixed = _summary(
            "POST-FIX (working tree)", scan(REPO / "platform" / "workflows")
        )

    print()
    ok = broken and not fixed
    print(
        f"{'SUCCESS' if ok else 'FAILED'}:d4-both-states "
        f"fires_on_broken={broken} silent_on_fixed={not fixed}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
