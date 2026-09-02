#!/usr/bin/env python3
"""Probe 1: promotion emits a PR diff and performs zero direct index writes.

Independent signal (1) of IMP-0071 evidence_requirement: index sha256 is
unchanged across a promotion attempt; a PR diff artifact is produced; the
direct-write path is rejected by the guard.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS / "marketplace"))

from index_model import clone, fixture_index, index_sha256  # noqa: E402
from promotion import (  # noqa: E402
    CONDITION_13_INLINE,
    DirectWritePromotionRefused,
    apply_promotion_to_index_file,
    promote_direct_write,
    promote_via_pr,
)

UNIT = "IMP-0071"
RECEIPT = REPO / "command-center/receipts/IMP-0071.json"
CONDITION_13_NEEDLE = "unsatisfiable as written under PR-ONLY"


def _fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    idx = fixture_index()
    live_copy = clone(idx)
    before = index_sha256(idx)

    promo = promote_via_pr(
        idx,
        package="echo",
        version="1.1.0-beta.1",
        from_channel="beta",
        to_channel="stable",
    )
    after = index_sha256(idx)
    if after != before:
        return _fail(f"index hash changed {before} -> {after}")
    if idx != live_copy:
        return _fail("caller index dict mutated")
    if not promo.index_hash_unchanged:
        return _fail("Promotion.index_hash_unchanged is false")
    if promo.direct_index_writes != 0:
        return _fail(f"direct_index_writes={promo.direct_index_writes}")
    if not promo.pr_diff or "echo" not in promo.pr_diff:
        return _fail("PR diff missing or does not name package")
    if "stable" not in promo.pr_diff or "beta" not in promo.pr_diff:
        return _fail("PR diff does not name the channel change")
    if promo.release_mode != "PR-ONLY":
        return _fail(f"release_mode={promo.release_mode}")

    guard_fired = False
    try:
        promote_direct_write(
            idx,
            package="echo",
            version="1.1.0-beta.1",
            from_channel="beta",
            to_channel="stable",
        )
    except DirectWritePromotionRefused:
        guard_fired = True
    if not guard_fired:
        return _fail("direct-write path was not rejected")

    file_guard_fired = False
    try:
        apply_promotion_to_index_file(Path("/tmp/imp-0071-must-not-write.json"), promo)
    except DirectWritePromotionRefused:
        file_guard_fired = True
    if not file_guard_fired:
        return _fail("index-file write path was not rejected")

    if RECEIPT.is_file():
        text = RECEIPT.read_text(encoding="utf-8")
        if "SUCCESS:IMP-0071" not in text:
            return _fail("receipt missing SUCCESS:IMP-0071")
        if CONDITION_13_NEEDLE not in text and CONDITION_13_INLINE not in text:
            return _fail("receipt does not state condition 13 unsatisfiable inline")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return _fail(f"receipt self-declared {st}")

    payload = {
        "probe": "probe1-promotion-pr-only",
        "unit_id": UNIT,
        "pr_artifact_produced": True,
        "pr_diff_sha256": hashlib.sha256(promo.pr_diff.encode("utf-8")).hexdigest(),
        "pr_diff_bytes": len(promo.pr_diff.encode("utf-8")),
        "direct_index_writes": promo.direct_index_writes,
        "index_sha256_before": before,
        "index_sha256_after": after,
        "index_hash_unchanged": True,
        "direct_write_guard_fired": True,
        "index_file_write_guard_fired": True,
        "release_mode": promo.release_mode,
        "condition_13_inline": CONDITION_13_INLINE,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"before={before} after={after} unchanged=True "
        f"direct_writes=0 guard_fired=True"
    )
    print(f"SUCCESS:{UNIT}-probe1 promotion PR-diff and zero direct index writes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
