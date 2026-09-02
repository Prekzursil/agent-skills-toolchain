#!/usr/bin/env python3
"""Named probe 2: teardown refuses when neither proof is available.

Both-states:
  * dirty worktree on main, unique bytes, no PR → REFUSE (fires on bad)
  * same unique bytes harvested into a preserve store → AUTHORIZE (silent on good)
  * unique bytes + MERGED PR (content still unique) → AUTHORIZE via PR
  * OPEN PR with ancestry-shaped fields → still REFUSE

Out-of-band: execute=True on the unproven tree must leave the canary file
on disk. Naive ancestry authorization would DELETE this tree (EQUAL on
main) — production must disagree.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from worktree_shard import (  # noqa: E402
    UNPROVEN_TEARDOWN,
    build_pr_merged_unique_fixture,
    build_unproven_fixture,
    harvest_unique_into,
    naive_ancestry_authorize,
    teardown_shard,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0446-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0446-p2-") as raw:
        tmp = Path(raw)

        bad = build_unproven_fixture(tmp / "unproven")
        canary = bad["unique_path"]
        refused = teardown_shard(
            worktree=bad["worktree"],
            repo=bad["repo"],
            shard_id="unproven",
            main_ref=bad["main_ref"],
            preserve_roots=bad["preserve_roots"],
            execute=True,
        )
        if refused.authorized:
            return fail("unproven teardown was authorized")
        if refused.refused_reason != UNPROVEN_TEARDOWN:
            return fail(f"refused_reason={refused.refused_reason} want {UNPROVEN_TEARDOWN}")
        if refused.executed:
            return fail("unproven teardown executed a delete")
        if not refused.worktree_still_present or not Path(bad["worktree"]).exists():
            return fail("unproven execute=True removed the worktree")
        if not canary.is_file():
            return fail("canary unique file missing after refused teardown")
        if canary.read_bytes() != bad["unique_bytes"]:
            return fail("canary bytes changed after refused teardown")
        naive = naive_ancestry_authorize(refused.ancestry)
        if not naive:
            return fail(
                "ancestry route did not judge dirty-on-main as safe "
                f"(the dangerous wrong answer): {refused.ancestry.as_dict()}"
            )
        if naive == refused.authorized:
            return fail("production matched ancestry on the unproven tree")
        if refused.ancestry_used_as_authorization:
            return fail("production used ancestry as authorization")

        store = tmp / "preserve-store"
        harvest_unique_into(store, canary, bad["unique_rel"])
        good = teardown_shard(
            worktree=bad["worktree"],
            repo=bad["repo"],
            shard_id="unproven",
            main_ref=bad["main_ref"],
            preserve_roots=[bad["repo"], store],
            execute=False,
        )
        if not good.authorized:
            return fail(f"harvested unique bytes still refused: {good.as_dict()}")
        content_ok = any(p.kind == "content-digest" and p.ok for p in good.proofs)
        if not content_ok:
            return fail("good state was not authorized by content-digest")

        pr_fx = build_pr_merged_unique_fixture(tmp / "pr-merged")
        via_pr = teardown_shard(
            worktree=pr_fx["worktree"],
            repo=pr_fx["repo"],
            shard_id="pr-merged",
            main_ref=pr_fx["main_ref"],
            preserve_roots=pr_fx["preserve_roots"],
            pr_state=pr_fx["pr_state"],
            execute=False,
        )
        if not via_pr.authorized:
            return fail(f"MERGED PR did not authorize unique-bytes tree: {via_pr.as_dict()}")
        pr_ok = any(p.kind == "merged-pr" and p.ok for p in via_pr.proofs)
        content_still_fail = any(
            p.kind == "content-digest" and not p.ok for p in via_pr.proofs
        )
        if not pr_ok or not content_still_fail:
            return fail("PR route did not authorize independently of content")

        open_pr = teardown_shard(
            worktree=pr_fx["worktree"],
            repo=pr_fx["repo"],
            shard_id="pr-open",
            main_ref=pr_fx["main_ref"],
            preserve_roots=pr_fx["preserve_roots"],
            pr_state={
                "state": "OPEN",
                "ahead": 0,
                "commits_ahead": 0,
                "is_ancestor": True,
                "merged": False,
            },
            execute=True,
        )
        if open_pr.authorized:
            return fail("OPEN PR with ancestry-shaped fields authorized teardown")
        if not Path(pr_fx["worktree"]).exists():
            return fail("OPEN-PR execute=True deleted the worktree")

        payload = {
            "probe": "probe2-unproven-teardown",
            "unit_id": "IMP-0446",
            "fired_on_unproven": True,
            "silent_on_harvested": True,
            "refused_reason": refused.refused_reason,
            "canary_survived_execute": True,
            "ancestry_would_have_deleted": True,
            "production_disagreed_with_ancestry": True,
            "merged_pr_authorizes_unique_bytes": True,
            "open_pr_with_ancestry_fields_refused": True,
            "unproven_side_by_side": refused.side_by_side,
            "harvested_side_by_side": good.side_by_side,
            "both_states": True,
            "pass": True,
        }
        print(json.dumps(payload, sort_keys=True, default=str))
        print(
            "fired_on_unproven=True silent_on_harvested=True "
            "canary_survived=True ancestry_would_delete=True "
            "merged_pr_ok=True open_pr_refused=True"
        )
        print("SUCCESS:IMP-0446-probe2 unproven teardown refused; both-states")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
