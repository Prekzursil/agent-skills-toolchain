#!/usr/bin/env python3
"""Named probe 2: would-revert paths listed; author deletions not misclassified.

Re-derives the verdict from raw git trees before reading the artifact conclusion.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402
from change_surface import (  # noqa: E402
    ls_tree_paths,
    merge_base,
    surface_from_spec,
    would_revert_paths,
)
from schema_local import domain  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0029-change-surface.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0029-probe2 {msg}")
    return 1


def main() -> int:
    # Independent re-derivation first (reviewer requirement): build fixture, compute
    # would-revert from ls-tree set difference, then only afterwards consult the artifact.
    from tempfile import TemporaryDirectory

    with TemporaryDirectory(prefix="cnf0029-p2-") as tmp:
        root = Path(tmp)
        meta = S.build_fixture(root)
        mb = merge_base(root, S.INTEGRATION, S.STALE)
        derived = would_revert_paths(root, S.INTEGRATION, S.STALE, mb)
        three_removed = set(
            surface_from_spec(root, f"{S.INTEGRATION}...{S.STALE}")["removed"]
        )
        gained = ls_tree_paths(root, S.INTEGRATION) - ls_tree_paths(root, mb)
        if set(derived) != gained:
            return fail(f"would-revert {derived} != gained-on-base {sorted(gained)}")
        if "obsolete.txt" not in three_removed:
            return fail("author deletion obsolete.txt missing from three-dot removed")
        if "obsolete.txt" in derived:
            return fail("author deletion obsolete.txt misclassified as would-revert")
        if not derived or len(derived) != S.POST_FORK_COUNT:
            return fail(f"would-revert count {len(derived)} want {S.POST_FORK_COUNT}")
        for rel in meta["post_fork_paths"]:
            if rel not in derived:
                return fail(f"missing would-revert path {rel}")
        derived_mb = mb

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = domain(doc)
    conclusion = str(payload.get("answer") or doc.get("answer") or "")
    branches = {
        b.get("name"): b
        for b in (payload.get("branches") or doc.get("branches") or [])
        if isinstance(b, dict)
    }
    art_stale = branches.get(S.STALE) or {}
    recorded = list(art_stale.get("would_revert") or [])
    if recorded != derived:
        return fail(f"artifact would-revert {recorded} != derived {derived}")
    if art_stale.get("merge_base_sha") != derived_mb:
        return fail("merge-base SHA mismatch vs independent derivation")
    if "obsolete.txt" in recorded:
        return fail("artifact listed author deletion as would-revert")
    if not art_stale.get("stale_branch_would_revert"):
        return fail("artifact did not flag stale-branch-would-revert")
    if "would-revert" not in conclusion.lower() and "gained after" not in conclusion.lower():
        return fail("artifact conclusion missing would-revert finding")

    out = {
        "probe": "probe2-would-revert",
        "unit_id": "CNF-0029",
        "pass": True,
        "would_revert_count": len(derived),
        "would_revert": derived,
        "merge_base_sha": derived_mb,
        "author_deletion_not_flagged": "obsolete.txt",
        "independent": True,
        "read_conclusion_after_derivation": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"would-revert={len(derived)} merge-base={derived_mb} "
        f"author-deletion-excluded=obsolete.txt"
    )
    print("SUCCESS:CNF-0029-probe2 would-revert listed per path; author delete excluded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
