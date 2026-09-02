#!/usr/bin/env python3
"""Probe 1: apply-then-revert tree-hash equality; revert touches no unrelated file.

Catalog tests: integration apply-then-revert tree-hash equality;
safety: revert touches no unrelated file.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixture import UNRELATED, build_tree, in_band, out_of_band  # noqa: E402
from selfimprove.retain import DROP, KEEP, decide, take_snapshot  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0373.json"
SENTINEL = "SUCCESS:IMP-0373"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0373-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0373-p1-") as td:
        root = Path(td) / "tree"
        ledger = Path(td) / "retention.jsonl"
        originals = build_tree(root)
        unrelated_before = (root / "unrelated.txt").read_bytes()
        pre = take_snapshot(root)

        changes = {
            "change.txt": b"candidate-mutated-change\n",
            "nested/created.txt": b"candidate-created\n",
        }
        out = decide(root, changes, in_band(), ledger, "p1-neutral")
        post = take_snapshot(root)

        if out.decision != DROP:
            return fail(f"neutral candidate was {out.decision}, expected REVERT")
        if not out.hashes_equal or pre.tree_hash != post.tree_hash:
            return fail(
                f"tree hash after revert pre={pre.tree_hash} post={post.tree_hash}"
            )
        if out.touched_outside_modified:
            return fail(f"revert touched unrelated {out.touched_outside_modified}")
        if (root / "unrelated.txt").read_bytes() != unrelated_before:
            return fail("unrelated.txt bytes changed across revert")
        if unrelated_before != UNRELATED:
            return fail("fixture unrelated bytes drifted")
        for rel, data in originals.items():
            live = (root / rel).read_bytes()
            if live != data:
                return fail(f"after revert {rel} != original")
        if (root / "nested" / "created.txt").exists():
            return fail("created candidate file survived revert")

        pre_keep = take_snapshot(root)
        keep_out = decide(
            root,
            {"change.txt": b"kept-because-measured\n"},
            out_of_band(),
            ledger,
            "p1-keep",
        )
        if keep_out.decision != KEEP:
            return fail(f"measured improvement was {keep_out.decision}, expected RETAIN")
        if keep_out.hashes_equal or keep_out.post_tree_hash == pre_keep.tree_hash:
            return fail("RETAIN left tree hash unchanged")
        if (root / "change.txt").read_bytes() != b"kept-because-measured\n":
            return fail("RETAIN did not keep candidate bytes")
        if (root / "unrelated.txt").read_bytes() != UNRELATED:
            return fail("RETAIN touched unrelated.txt")

    receipt_ok = RECEIPT.is_file() and SENTINEL in RECEIPT.read_text(encoding="utf-8")
    payload = {
        "probe": "probe1-apply-revert-tree-hash",
        "unit_id": "IMP-0373",
        "revert_pre_tree_hash": pre.tree_hash,
        "revert_post_tree_hash": post.tree_hash,
        "revert_hashes_equal": True,
        "touched_outside_modified": out.touched_outside_modified,
        "retain_decision": keep_out.decision,
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": receipt_ok if RECEIPT.is_file() else None,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"revert_hash_equal=True pre={pre.tree_hash[:12]} "
        f"unrelated_untouched=True retain={keep_out.decision}"
    )
    print("SUCCESS:IMP-0373-probe1 apply-then-revert tree-hash equality; no unrelated touch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
