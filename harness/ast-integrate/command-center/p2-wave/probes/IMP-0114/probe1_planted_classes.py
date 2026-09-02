#!/usr/bin/env python3
"""Probe 1: linter findings over one planted defect of each class.

Both-states control in the same process: a clean clone yields zero findings.
A detector that is red on both, or green on both, fails.

This is evidence signal (1) from the catalog.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

import index_linter as linter  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp-0114-p1-") as td:
        root = Path(td)
        _store, _index, planted = linter.plant_one_of_each_defect(root / "dirty")
        dirty = linter.lint_root(root / "dirty")
        linter.plant_clean(root / "clean")
        clean = linter.lint_root(root / "clean")

        kinds = dirty.kinds
        missing = sorted(linter.REQUIRED_KINDS - kinds)
        dangling_named = any(
            f.kind == linter.KIND_DANGLING and f.entry_id == planted["dangling_id"]
            for f in dirty.findings
        )
        orphan_named = planted["orphan_digest"] in dirty.orphan_digests
        duplicate_named = any(
            f.kind == linter.KIND_DUPLICATE and f.entry_id == planted["duplicate_id"]
            for f in dirty.findings
        )
        mismatch_named = any(
            f.kind == linter.KIND_DIGEST and f.entry_id == planted["mismatch_id"]
            for f in dirty.findings
        )
        unresolvable_named = any(
            f.kind == linter.KIND_UNRESOLVABLE
            and f.entry_id == planted["unresolvable_from"]
            and f.detail == planted["unresolvable_dep"]
            for f in dirty.findings
        )
        fired_on_bad = (
            not missing
            and dangling_named
            and orphan_named
            and duplicate_named
            and mismatch_named
            and unresolvable_named
            and dirty.walked_blob_store
            and dirty.hashed_blobs >= 1
        )
        silent_on_good = (
            clean.findings == []
            and clean.clean
            and clean.walked_blob_store
            and clean.hashed_blobs == len(linter.CLEAN_PACKAGES)
        )
        result = {
            "probe": "probe1-planted-defect-classes",
            "unit_id": "IMP-0114",
            "fired_on_bad": fired_on_bad,
            "silent_on_good": silent_on_good,
            "dirty_kinds": sorted(kinds),
            "missing_kinds": missing,
            "dangling_named": dangling_named,
            "orphan_named": orphan_named,
            "duplicate_named": duplicate_named,
            "mismatch_named": mismatch_named,
            "unresolvable_named": unresolvable_named,
            "dirty_walked_blob_store": dirty.walked_blob_store,
            "dirty_hashed_blobs": dirty.hashed_blobs,
            "clean_findings": len(clean.findings),
            "clean_walked_blob_store": clean.walked_blob_store,
            "pass": fired_on_bad and silent_on_good,
        }
        print(json.dumps(result, sort_keys=True))
        print(
            f"kinds={sorted(kinds)} missing={missing} "
            f"fired_on_bad={fired_on_bad} silent_on_good={silent_on_good}"
        )
        if not result["pass"]:
            print(
                "FAILED:IMP-0114-probe1 planted classes not all named "
                "or clean control fired"
            )
            return 1
        print(
            "SUCCESS:IMP-0114-probe1 five planted classes named; "
            "clean index silent in the same run"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
