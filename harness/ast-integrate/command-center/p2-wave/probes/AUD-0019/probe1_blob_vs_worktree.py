#!/usr/bin/env python3
"""Probe 1: byte-compare git cat-file -p against the working tree for every text path.

Never uses git archive as the blob source. Archive is only measured in the
three-route control on a known file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fixture_git as FG  # noqa: E402
import lib as L  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0019-probe1 {msg}")
    return 1


def run() -> dict:
    fx = FG.build_fixture()
    git_dir = Path(fx["git_dir"])
    work_tree = Path(fx["work_tree"])
    paths = L.list_blob_paths(git_dir)
    compared = L.compare_paths(git_dir, work_tree, paths)
    by_path = {row["path"]: row for row in compared["rows"]}
    three_pinned = L.three_route(git_dir, FG.PLANTED["archive_disagrees"])
    three_unmarked = L.three_route(git_dir, FG.PLANTED["unpinned_identical"])
    live_git = L.live_git_present(L.REPO)
    live_blob: dict = {
        "status": "CHECKED" if live_git else "NOT-CHECKED",
        "reason": (
            None
            if live_git
            else (
                "this Linux worktree is not a git checkout; no HEAD blobs exist "
                "to cat-file"
            )
        ),
        "path_count": 0,
        "counts": {},
        "eol_only_paths": [],
    }
    if live_git:
        git_dir_live = L.REPO / ".git"
        names = [
            n
            for n in L.git_bytes(
                ["ls-tree", "-r", "--name-only", "HEAD"],
                env=L.git_env(git_dir_live, L.REPO),
            )
            .decode("utf-8")
            .splitlines()
            if n
        ]
        live_cmp = L.compare_paths(git_dir_live, L.REPO, names)
        live_blob = {
            "status": "CHECKED",
            "reason": None,
            "path_count": live_cmp["row_count"],
            "counts": live_cmp["counts"],
            "eol_only_paths": [
                r["path"] for r in live_cmp["rows"] if r["class"] == "eol-only"
            ],
        }
    inventory = L.live_worktree_eol_inventory(L.REPO)
    return {
        "probe": "probe1-blob-vs-worktree",
        "blob_recipe": "git cat-file -p HEAD:<path>",
        "archive_used_as_blob_source": False,
        "fixture": {
            "construction": fx["construction"],
            "commit": fx["commit"],
            "path_count": len(paths),
            "counts": compared["counts"],
            "rows": compared["rows"],
            "planted_eol_only": by_path.get(FG.PLANTED["eol_only"]),
            "planted_content": by_path.get(FG.PLANTED["content"]),
            "planted_identical": by_path.get(FG.PLANTED["identical_pinned"]),
        },
        "three_route_control": {
            "pinned_eol_crlf": three_pinned,
            "unmarked_file": three_unmarked,
        },
        "live_git_checkout": live_git,
        "live_blob_vs_worktree": live_blob,
        "live_worktree_eol_inventory": inventory,
        "core_autocrlf": L.read_autocrlf(),
    }


def main() -> int:
    data = run()
    fx = data["fixture"]
    eol_row = fx["planted_eol_only"] or {}
    content_row = fx["planted_content"] or {}
    ident_row = fx["planted_identical"] or {}
    if eol_row.get("class") != "eol-only":
        return fail(f"planted CRLF worktree not classified eol-only: {eol_row}")
    if content_row.get("class") != "content":
        return fail(f"planted content mutation classified as {content_row}")
    if ident_row.get("class") != "identical":
        return fail(f"pinned identical path drifted: {ident_row}")
    pinned = data["three_route_control"]["pinned_eol_crlf"]
    unmarked = data["three_route_control"]["unmarked_file"]
    if not pinned.get("archive_differs_from_blob"):
        return fail("archive did not disagree on eol=crlf notes.txt")
    if not pinned.get("cat_file_equals_show"):
        return fail("cat-file and show disagreed on control file")
    if not pinned.get("identical_after_lf_normalisation"):
        return fail("three routes differ by more than line endings")
    if not unmarked.get("all_three_agree"):
        return fail("unmarked file should agree on Linux archive vs blob")
    if data["archive_used_as_blob_source"]:
        return fail("archive was used as blob source")
    print(json.dumps(data, sort_keys=True, default=str))
    print(
        "fixture_eol_only={0} archive_disagrees={1} live_git={2} live_blob={3}".format(
            fx["counts"]["eol-only"],
            pinned["archive_differs_from_blob"],
            data["live_git_checkout"],
            data["live_blob_vs_worktree"]["status"],
        )
    )
    print("SUCCESS:AUD-0019-probe1 blob-vs-worktree cat-file-not-archive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
