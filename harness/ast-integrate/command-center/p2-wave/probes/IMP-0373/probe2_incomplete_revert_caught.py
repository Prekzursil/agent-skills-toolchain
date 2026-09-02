#!/usr/bin/env python3
"""Probe 2: negative control — a revert that misses one file is caught by tree hash.

Also: extra-file touch is caught by the modified-set check; an assumed noise band
cannot count as measured improvement; ledger rewrite is refused.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixture import assumed_band, build_tree  # noqa: E402
from selfimprove.retain import (  # noqa: E402
    DROP,
    AppendOnlyError,
    IncompleteRevertError,
    SafetyError,
    apply_patch,
    check_revert,
    decide,
    load_jsonl,
    measured_improvement,
    reject_rewrite,
    revert_patch,
    snap_diff,
    take_snapshot,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0373-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0373-p2-") as td:
        root = Path(td) / "tree"
        build_tree(root)
        pre = take_snapshot(root)
        applied = apply_patch(
            root,
            {
                "change.txt": b"mut-a\n",
                "keep.txt": b"mut-b\n",
            },
        )
        report = revert_patch(
            root, applied.preimages, applied.created_dirs, skip=["keep.txt"]
        )
        post = take_snapshot(root)
        diff = snap_diff(pre, post)
        if post.tree_hash == pre.tree_hash:
            return fail("incomplete revert produced identical tree hash (detector blind)")
        if "keep.txt" not in diff["changed"]:
            return fail(f"missed file not in census diff: {diff}")
        if (root / "keep.txt").read_bytes() != b"mut-b\n":
            return fail("skipped file was unexpectedly restored")
        caught_hash = False
        try:
            check_revert(pre, post, applied.modified_files, report.touched)
        except IncompleteRevertError:
            caught_hash = True
        if not caught_hash:
            return fail("check_revert did not raise IncompleteRevertError")

        root2 = Path(td) / "tree2"
        build_tree(root2)
        pre2 = take_snapshot(root2)
        applied2 = apply_patch(root2, {"change.txt": b"x\n"})
        report2 = revert_patch(
            root2,
            applied2.preimages,
            applied2.created_dirs,
            extra_touch=["unrelated.txt"],
        )
        post2 = take_snapshot(root2)
        caught_safety = False
        try:
            check_revert(pre2, post2, applied2.modified_files, report2.touched)
        except SafetyError:
            caught_safety = True
        if not caught_safety:
            return fail("extra-touch revert was not caught")
        if "unrelated.txt" not in report2.touched:
            return fail("extra-touch was not recorded in touched set")

        if measured_improvement(assumed_band()):
            return fail("assumed noise band counted as measured improvement")
        root3 = Path(td) / "tree3"
        build_tree(root3)
        original = (root3 / "change.txt").read_bytes()
        ledger = Path(td) / "retention.jsonl"
        out = decide(
            root3,
            {"change.txt": b"should-not-keep\n"},
            assumed_band(),
            ledger,
            "p2-assumed",
        )
        if out.decision != DROP:
            return fail(f"assumed-band candidate was {out.decision}")
        if (root3 / "change.txt").read_bytes() != original:
            return fail("assumed-band candidate was not reverted")
        rewrite_refused = False
        try:
            reject_rewrite(ledger)
        except AppendOnlyError:
            rewrite_refused = True
        if not rewrite_refused:
            return fail("ledger rewrite was not refused")
        rows = load_jsonl(ledger)
        if len(rows) != 1 or rows[0]["decision"] != DROP:
            return fail(f"ledger rows unexpected: {rows}")

    payload = {
        "probe": "probe2-incomplete-revert-caught",
        "unit_id": "IMP-0373",
        "incomplete_hashes_differ": True,
        "missed_file_in_diff": "keep.txt" in diff["changed"],
        "incomplete_detector_fired": True,
        "extra_touch_detector_fired": True,
        "assumed_band_reverted": True,
        "ledger_rewrite_refused": True,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "incomplete_caught=True extra_touch_caught=True "
        "assumed_band_reverted=True ledger_append_only=True"
    )
    print("SUCCESS:IMP-0373-probe2 incomplete revert caught by tree hash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
