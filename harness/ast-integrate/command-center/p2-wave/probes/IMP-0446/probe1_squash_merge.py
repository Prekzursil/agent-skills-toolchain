#!/usr/bin/env python3
"""Named probe 1: squash-merge fixture — content SAFE, ancestry UNSAFE.

A fully squash-merged feature branch still reports AHEAD. The content
route must authorize teardown; the ancestry route must not. Production
teardown must follow the content route (and must actually remove the
worktree when execute=True). Two concurrently provisioned shards must
not share a git index.
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
    build_squash_merge_fixture,
    init_fixture_repo,
    naive_ancestry_authorize,
    provision_shard,
    staged_names,
    teardown_shard,
)
from worktree_shard.provisioner import git  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0446-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0446-p1-") as raw:
        tmp = Path(raw)
        fx = build_squash_merge_fixture(tmp / "squash")
        repo = fx["repo"]
        wt = fx["worktree"]

        decision = teardown_shard(
            worktree=wt,
            repo=repo,
            shard_id="squash-feature",
            main_ref=fx["main_ref"],
            preserve_roots=fx["preserve_roots"],
            execute=False,
        )
        ancestry = decision.ancestry
        content_ok = any(p.kind == "content-digest" and p.ok for p in decision.proofs)
        pr_ok = any(p.kind == "merged-pr" and p.ok for p in decision.proofs)
        naive = naive_ancestry_authorize(ancestry)

        if not ancestry.reports_ahead:
            return fail(f"squash-merged branch did not report AHEAD: {ancestry.as_dict()}")
        if naive:
            return fail("ancestry route judged squash-merged branch safe (want unsafe)")
        if not content_ok:
            return fail(f"content route failed on squash-merged tree: {decision.as_dict()}")
        if pr_ok:
            return fail("PR route was not supposed to fire on this fixture")
        if not decision.authorized:
            return fail("production refused content-proven squash-merged teardown")
        if decision.ancestry_used_as_authorization:
            return fail("production marked ancestry as authorization")
        if not decision.side_by_side.get("routes_disagree"):
            return fail("side-by-side did not record ancestry/content disagreement")
        if naive == decision.authorized:
            return fail("production authorization matched ancestry (must disagree)")

        canary = wt / "tracked.txt"
        if not canary.is_file():
            return fail("feature worktree missing tracked.txt before execute")
        executed = teardown_shard(
            worktree=wt,
            repo=repo,
            shard_id="squash-feature",
            main_ref=fx["main_ref"],
            preserve_roots=fx["preserve_roots"],
            execute=True,
        )
        if not executed.executed:
            return fail("content-proven teardown did not execute")
        if executed.worktree_still_present or wt.exists():
            return fail("content-proven teardown left the worktree on disk")

        shard_repo = init_fixture_repo(tmp / "shared")
        a = provision_shard(shard_repo, "IMP-0446-a", parent_dir=tmp / "shards")
        b = provision_shard(shard_repo, "IMP-0446-b", parent_dir=tmp / "shards")
        if a.index_path == b.index_path:
            return fail(f"shards share index {a.index_path}")
        if a.path == b.path:
            return fail("shards share worktree path")
        (a.path / "a-only.txt").write_text("alpha-bytes\n", encoding="utf-8")
        (b.path / "b-only.txt").write_text("beta-bytes\n", encoding="utf-8")
        git(a.path, "add", "a-only.txt")
        git(b.path, "add", "b-only.txt")
        staged_a = staged_names(a.path)
        staged_b = staged_names(b.path)
        if "a-only.txt" not in staged_a or "a-only.txt" in staged_b:
            return fail(f"index contamination A->{staged_a} B->{staged_b}")
        if "b-only.txt" not in staged_b or "b-only.txt" in staged_a:
            return fail(f"index contamination B->{staged_b} A->{staged_a}")

        payload = {
            "probe": "probe1-squash-merge",
            "unit_id": "IMP-0446",
            "ancestry": ancestry.as_dict(),
            "content_route_safe": True,
            "ancestry_route_safe": False,
            "reports_ahead": True,
            "production_authorized": True,
            "ancestry_used_as_authorization": False,
            "routes_disagree": True,
            "executed_teardown_removed_worktree": True,
            "shard_indexes_disjoint": True,
            "index_a": str(a.index_path),
            "index_b": str(b.index_path),
            "staged_a": staged_a,
            "staged_b": staged_b,
            "side_by_side": decision.side_by_side,
            "pass": True,
        }
        print(json.dumps(payload, sort_keys=True, default=str))
        print(
            "content_safe=True ancestry_safe=False reports_ahead=True "
            "production_authorized=True indexes_disjoint=True"
        )
        print("SUCCESS:IMP-0446-probe1 squash-merge content-safe ancestry-unsafe")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
