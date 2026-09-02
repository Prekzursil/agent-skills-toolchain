"""Catalog tests for TST-0101, run inside isolated sandboxes only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import gate as G  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center/receipts/TST-0101.json"


def artifact_payload(doc: dict) -> dict:
    """Measured surfaces live in extensions (receipt_core additionalProperties=false)."""
    ext = doc.get("extensions")
    if isinstance(ext, dict) and isinstance(ext.get("three_dot"), dict):
        return ext
    ev = doc.get("evidence")
    if isinstance(ev, dict):
        return ev
    return {}


def _fail(name: str, msg: str) -> dict:
    print(f"FAILED:{name} {msg}")
    return {"id": name, "result": "FAIL", "detail": msg}


def _pass(name: str, detail: dict) -> dict:
    print(json.dumps({"id": name, "result": "PASS", **detail}, sort_keys=True))
    return {"id": name, "result": "PASS", "detail": detail}


def test_gate_fails_on_a_stale_branch_proposing_mass_deletion() -> dict:
    name = "test_gate_fails_on_a_stale_branch_proposing_mass_deletion"
    with F.with_fixture("stale-mass-deletion") as box:
        bad = G.evaluate(box.root, "main", "HEAD")
        print(
            f"stale_mass three_dot files={bad.proposal.files_changed} "
            f"deletions={bad.proposal.deletions} deleted_paths={len(bad.proposal.deleted_paths)} "
            f"two_dot files={bad.two_dot.files_changed} deletions={bad.two_dot.deletions} "
            f"blocked={bad.blocked} range={bad.proposal.range}"
        )
        if G.THREE_DOT not in bad.proposal.range or bad.range_form != G.THREE_DOT:
            return _fail(name, "gate did not record a three-dot proposal range")
        if not bad.blocked or not bad.mass_deletion:
            return _fail(name, f"stale mass-deletion branch was not blocked: {bad.reason}")
        if len(bad.proposal.deleted_paths) < F.KEEP_FILES:
            return _fail(name, "three-dot surface missed keep-set deletions")
    with F.with_fixture("fresh-small") as box:
        good = G.evaluate(box.root, "main", "HEAD")
        print(
            f"fresh_small three_dot files={good.proposal.files_changed} "
            f"deletions={good.proposal.deletions} blocked={good.blocked} "
            f"unmerged={good.unmerged}"
        )
        if good.blocked or good.mass_deletion:
            return _fail(name, f"freshly based branch was blocked: {good.reason}")
        if good.proposal.deletions != 0:
            return _fail(name, "fresh branch three-dot surface is not deletion-free")
    return _pass(
        name,
        {
            "bad_blocked": True,
            "good_silent": True,
            "both_states": True,
            "three_dot_range": True,
        },
    )


def test_gate_uses_three_dot_not_two_dot() -> dict:
    name = "test_gate_uses_three_dot_not_two_dot"
    with F.with_fixture("stale-small-proposal") as box:
        result = G.evaluate(box.root, "main", "HEAD")
        decoy = G.decoy_two_dot_blocks(box.root, "main", "HEAD")
        three = result.proposal
        two = result.two_dot
        wt = result.worktree
        print(
            f"three_dot argv={three.argv} files={three.files_changed} "
            f"deletions={three.deletions} deleted={three.deleted_paths}"
        )
        print(
            f"two_dot argv={two.argv} files={two.files_changed} "
            f"deletions={two.deletions} deleted={len(two.deleted_paths)} "
            f"would_revert={len(result.would_revert_paths)}"
        )
        print(
            f"worktree files={wt.files_changed} deletions={wt.deletions} "
            f"surfaces_differ={result.surfaces_differ} decoy_blocks={decoy} "
            f"gate_blocked={result.blocked}"
        )
        if three.form != "three-dot" or G.THREE_DOT not in three.range:
            return _fail(name, f"proposal range is not three-dot: {three.range}")
        if G.TWO_DOT + G.TWO_DOT not in three.range:
            # three-dot is '...' which contains '..'; require exact '...'
            pass
        if three.range != f"main{G.THREE_DOT}HEAD":
            return _fail(name, f"unexpected proposal range {three.range}")
        if two.range != f"main{G.TWO_DOT}HEAD":
            return _fail(name, f"two-dot control range missing: {two.range}")
        if not result.surfaces_differ:
            return _fail(name, "three-dot and two-dot surfaces did not differ")
        if len(result.would_revert_paths) < F.NEWER_ON_MAIN:
            return _fail(
                name,
                f"two-dot did not expose newer-on-main would-reverts "
                f"({len(result.would_revert_paths)})",
            )
        if result.blocked:
            return _fail(name, "three-dot gate blocked a one-file proposal")
        if not decoy:
            return _fail(name, "two-dot decoy failed to block; the contrast is not evidenced")
        if wt.files_changed <= three.files_changed:
            return _fail(name, "worktree two-dot did not exceed the commit three-dot surface")
        if "README.md" not in wt.changed_paths and "README.md" not in wt.deleted_paths:
            return _fail(name, "worktree noise (README.md) did not enter the two-dot WT surface")
        if "README.md" in three.changed_paths or "README.md" in three.deleted_paths:
            return _fail(name, "worktree noise leaked into the three-dot proposal")
    return _pass(
        name,
        {
            "three_dot_range": "main...HEAD",
            "two_dot_range": "main..HEAD",
            "surfaces_differ": True,
            "decoy_two_dot_blocks": True,
            "gate_allows_small_stale_proposal": True,
            "worktree_noise_excluded": True,
        },
    )


def test_squash_merged_branch_is_not_treated_as_unmerged() -> dict:
    name = "test_squash_merged_branch_is_not_treated_as_unmerged"
    with F.with_fixture("squash-merged-ahead") as box:
        result = G.evaluate(box.root, "main", "HEAD")
        ahead = result.ahead
        print(
            f"squash ahead={ahead} behind={result.behind} "
            f"trees_identical={result.trees_identical} "
            f"squash_merged_ahead={result.squash_merged_ahead} "
            f"unmerged={result.unmerged} blocked={result.blocked} "
            f"two_dot_files={result.two_dot.files_changed} "
            f"three_dot_files={result.proposal.files_changed}"
        )
        if ahead <= 0:
            return _fail(name, "fixture did not demonstrate ancestry AHEAD after squash-merge")
        if not result.trees_identical:
            return _fail(name, "squash-merged trees should be identical")
        if not result.squash_merged_ahead:
            return _fail(name, "gate missed squash-merged AHEAD")
        if result.unmerged:
            return _fail(name, "squash-merged AHEAD was treated as unmerged")
        if result.blocked:
            return _fail(name, "squash-merged branch was blocked as a mass-deletion proposal")
        if result.two_dot.files_changed != 0:
            return _fail(name, "two-dot tip-to-tip should be empty when trees match")
        # Ancestry AHEAD is explicitly not a delete authorisation.
        if "delete" not in result.reason.lower() and "ahead" not in result.reason.lower():
            return _fail(name, f"reason did not name the ancestry trap: {result.reason}")
    return _pass(
        name,
        {
            "ahead": ahead,
            "unmerged": False,
            "squash_merged_ahead": True,
            "ancestry_is_not_delete_authorisation": True,
        },
    )


def run_all() -> list[dict]:
    return [
        test_gate_fails_on_a_stale_branch_proposing_mass_deletion(),
        test_gate_uses_three_dot_not_two_dot(),
        test_squash_merged_branch_is_not_treated_as_unmerged(),
    ]


if __name__ == "__main__":
    rows = run_all()
    failed = [r for r in rows if r.get("result") != "PASS"]
    if failed:
        print("FAILED:TST-0101 tests")
        raise SystemExit(1)
    print("SUCCESS:TST-0101-tests all three catalog tests")
    raise SystemExit(0)
