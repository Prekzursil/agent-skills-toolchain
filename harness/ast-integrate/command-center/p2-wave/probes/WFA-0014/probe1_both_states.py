#!/usr/bin/env python3
"""Probe 1: both-states squash-ahead vs genuinely-unique (catalog test 1).

Signal A is three-dot name-only. Signal B is cat-file -p byte compare.
A fully squash-merged branch must be ancestry-ahead AND unique_content=0.
A branch with a novel workflow blob must be unique_content>=1.
Two-tree diff of the squash pair must be empty (control that B is not A).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from fixtures import control_pack  # noqa: E402
from gitcmd import cat_file_p, git_show_path, three_dot_names, two_tree_names  # noqa: E402
from paths import workflow_bearing  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0014/probe1_both_states.py"
)


def _fail(msg: str) -> int:
    print(f"FAILED:WFA-0014-probe1 {msg}")
    return 1


def main() -> int:
    engine_src = (HERE / "engine.py").read_text(encoding="utf-8")
    gitcmd_src = (HERE / "gitcmd.py").read_text(encoding="utf-8")
    if "archive" in engine_src.split() or "git archive" in engine_src:
        return _fail("engine.py mentions git archive")
    if '"archive"' in gitcmd_src or "'archive'" in gitcmd_src:
        if "FORBIDDEN" not in gitcmd_src:
            return _fail("gitcmd.py archive mention is not the forbid list")
    if "..." not in engine_src and "...{" not in gitcmd_src:
        return _fail("three-dot operator missing from engine/gitcmd")
    if "cat-file" not in gitcmd_src:
        return _fail("gitcmd.py does not call cat-file")
    if "Path.exists" in engine_src or ".exists()" in engine_src:
        return _fail("engine.py must not probe working-tree existence")

    pack = control_pack()
    squash = pack["squash_ahead"]
    unique = pack["unique"]
    print(
        json.dumps(
            {
                "squash": {
                    "ancestry_ahead": squash["ancestry_ahead"],
                    "ahead_commit_count": squash["ahead_commit_count"],
                    "signal_a_path_count": squash["signal_a_path_count"],
                    "two_tree_path_count": squash["two_tree_path_count"],
                    "unique_content_count": squash["unique_content_count"],
                    "identical_to_main_count": squash["identical_to_main_count"],
                    "conflict_surface": squash["conflict_surface"],
                },
                "unique": {
                    "ancestry_ahead": unique["ancestry_ahead"],
                    "signal_a_path_count": unique["signal_a_path_count"],
                    "unique_content_count": unique["unique_content_count"],
                    "conflict_surface": unique["conflict_surface"],
                },
            },
            sort_keys=True,
        )
    )

    if not squash["ancestry_ahead"] or squash["ahead_commit_count"] < 1:
        return _fail("squash-merged branch is not ancestry-ahead")
    if squash["signal_a_path_count"] < 1:
        return _fail("signal A empty on squash-ahead; three-dot did not see the illusion")
    if squash["unique_content_count"] != 0:
        return _fail(
            f"squash unique_content_count={squash['unique_content_count']} want 0 (signal B)"
        )
    if squash["identical_to_main_count"] < 1:
        return _fail("squash fixture produced no IDENTICAL-TO-MAIN hit")
    if squash["two_tree_path_count"] != 0:
        return _fail(
            f"two-tree diff nonempty ({squash['two_tree_path_count']}); "
            "squash trees should match, proving A is three-dot not two-tree"
        )
    if squash["deletion_recommended"]:
        return _fail("squash branch recommended deletion")

    if not unique["ancestry_ahead"]:
        return _fail("unique-content branch is not ancestry-ahead")
    if unique["unique_content_count"] < 1:
        return _fail("unique fixture unique_content_count=0; detector is dead")
    if unique["signal_a_path_count"] < 1:
        return _fail("unique fixture signal A empty")
    classes = {h["classification"] for h in unique["hits"]}
    if "GENUINELY-UNIQUE" not in classes:
        return _fail(f"unique fixture classes={classes}")

    # Independent verifier: git show (not cat-file) on the unique path.
    # Recreate is expensive; trust hits then re-hash via show on a fresh unique repo
    # by reading blob_sha256 already computed from cat-file and requiring git show
    # equality is done in probe2. Here we assert the two-tree vs three-dot split
    # using gitcmd helpers against a rebuilt squash repo? control_pack already
    # returned two_tree_path_count from engine. Additionally inspect gitcmd API:
    from fixtures import build_squash_ahead, build_unique, temp_repo

    with temp_repo() as repo:
        build_squash_ahead(repo)
        a = [p for p in three_dot_names(repo, "main", "feature/squash-merged") if workflow_bearing(p)]
        b = [p for p in two_tree_names(repo, "main", "feature/squash-merged") if workflow_bearing(p)]
        if not a:
            return _fail("direct three-dot names empty")
        if b:
            return _fail(f"direct two-tree names nonempty: {b}")
        for path in a:
            main_blob = cat_file_p(repo, "main", path)
            branch_blob = cat_file_p(repo, "feature/squash-merged", path)
            show_main = git_show_path(repo, "main", path)
            show_branch = git_show_path(repo, "feature/squash-merged", path)
            if main_blob is None or branch_blob is None:
                return _fail(f"squash path {path} missing on main or branch")
            if main_blob != branch_blob:
                return _fail(f"squash path {path} bytes differ under cat-file")
            if show_main != main_blob or show_branch != branch_blob:
                return _fail(f"git show disagreed with cat-file on {path}")

    with temp_repo() as repo:
        build_unique(repo)
        names = [
            p
            for p in three_dot_names(repo, "main", "feature/unique-gate")
            if workflow_bearing(p)
        ]
        if ".github/workflows/unique-gate.yml" not in names:
            return _fail(f"unique path missing from three-dot: {names}")
        main_blob = cat_file_p(repo, "main", ".github/workflows/unique-gate.yml")
        branch_blob = cat_file_p(repo, "feature/unique-gate", ".github/workflows/unique-gate.yml")
        if main_blob is not None:
            return _fail("unique path unexpectedly present on main")
        if not branch_blob:
            return _fail("unique path missing on branch")
        if git_show_path(repo, "feature/unique-gate", ".github/workflows/unique-gate.yml") != branch_blob:
            return _fail("git show != cat-file on unique blob")

    print("SUCCESS:WFA-0014-probe1 both-states squash unique=0 / novel unique>=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
