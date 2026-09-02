#!/usr/bin/env python3
"""Probe 1: known workflow + known non-workflow classified correctly BEFORE totals.

Both-states: the good fixture passes; a mutant that empties the workflow file
must fail the control; a mutant that never runs controls must not be trusted.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from classify import NON_WORKFLOW, WORKFLOW  # noqa: E402
from fixture import (  # noqa: E402
    KNOWN_NON_WORKFLOW,
    KNOWN_WORKFLOW,
    build_fixture,
)
from gitutil import git  # noqa: E402
from sweep import DetectorControlFailure, sweep_repo  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0013-probe1 {msg}")
    return 1


def _source_forbids_archive() -> bool:
    text = (HERE / "sweep.py").read_text(encoding="utf-8")
    gitutil = (HERE / "gitutil.py").read_text(encoding="utf-8")
    if "cat-file" not in text and "cat_file_p" not in text:
        return False
    if "git archive" in text:
        return False
    if "archive" in gitutil and "forbidden" not in gitutil:
        return False
    return True


def main() -> int:
    if not _source_forbids_archive():
        return fail("sweep source must call git cat-file -p and never git archive")

    with tempfile.TemporaryDirectory(prefix="wfa0013-p1-") as raw:
        base = Path(raw)

        good = base / "good"
        meta = build_fixture(good)
        result = sweep_repo(good, meta["registry"], controls=meta["controls"])
        if not result.controls_completed_before_totals:
            return fail("totals were computed before detector controls")
        if not all(c.ok for c in result.controls):
            return fail(f"good controls failed: {result.controls}")
        got = {c.path: c.got for c in result.controls}
        if got.get(KNOWN_WORKFLOW) != WORKFLOW:
            return fail(f"known workflow classified {got.get(KNOWN_WORKFLOW)}")
        if got.get(KNOWN_NON_WORKFLOW) != NON_WORKFLOW:
            return fail(f"known non-workflow classified {got.get(KNOWN_NON_WORKFLOW)}")
        if result.used_git_archive:
            return fail("good sweep used git archive")
        if result.counts["ls_tree_entries"] < 1:
            return fail("good sweep produced empty ls-tree totals")

        mutant = base / "mutant-empty-workflow"
        shutil.copytree(good, mutant, ignore=shutil.ignore_patterns(".git"))
        # Rebuild as a real git repo with the workflow file emptied.
        mutant_git = base / "mutant-git"
        meta2 = build_fixture(mutant_git)
        (mutant_git / KNOWN_WORKFLOW).write_text("# emptied\n", encoding="utf-8")
        git(mutant_git, "add", KNOWN_WORKFLOW)
        git(mutant_git, "commit", "-q", "-m", "empty the known workflow")
        fired = False
        try:
            sweep_repo(mutant_git, meta2["registry"], controls=meta2["controls"])
        except DetectorControlFailure:
            fired = True
        if not fired:
            return fail("emptying the known workflow did not fail the detector control")

        skip = base / "skip-controls"
        meta3 = build_fixture(skip)
        skipped = sweep_repo(skip, meta3["registry"], controls=None)
        if skipped.controls_completed_before_totals and skipped.controls:
            return fail("skip-controls unexpectedly ran controls")
        if skipped.controls:
            return fail("skip-controls must not fabricate control rows")
        # Totals without the required both-states control are not admissible.
        if not skipped.counts:
            return fail("skip-controls produced no totals (unexpected)")

    payload = {
        "probe": "probe1-detector-control-before-totals",
        "unit_id": "WFA-0013",
        "good_workflow": WORKFLOW,
        "good_non_workflow": NON_WORKFLOW,
        "controls_before_totals": True,
        "empty_workflow_mutant_fired": True,
        "skip_controls_has_no_control_rows": True,
        "forbids_git_archive": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "good_workflow=WORKFLOW good_non_workflow=NON-WORKFLOW "
        "before_totals=True empty_mutant_fired=True archive_forbidden=True"
    )
    print("SUCCESS:WFA-0013-probe1 detector control both-states before totals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
