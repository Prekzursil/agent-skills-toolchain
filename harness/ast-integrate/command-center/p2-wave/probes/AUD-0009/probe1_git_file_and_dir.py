#!/usr/bin/env python3
"""Probe 1: every .git FILE or directory. Submodule .git is a FILE.

Control: fixture with both forms. Independent recount via POSIX find.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from finder import find_git_find_cmd, find_git_os_walk, paths_of  # noqa: E402
from scan import live_git_inventory, repo_root  # noqa: E402


def build_both_forms_fixture(root: Path) -> None:
    nested = root / "nested-repo" / ".git"
    nested.mkdir(parents=True)
    (nested / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (nested / "config").write_text("[core]\n\trepositoryformatversion = 0\n", encoding="utf-8")
    sub = root / "submodule-style"
    sub.mkdir()
    (sub / ".git").write_text("gitdir: ../nested-repo/.git\n", encoding="utf-8")
    decoy = root / "not-a-git"
    decoy.mkdir()
    (decoy / "git").write_text("decoy file named git, not .git\n", encoding="utf-8")


def run_control() -> dict:
    with tempfile.TemporaryDirectory(prefix="aud0009-git-") as tmp:
        root = Path(tmp)
        build_both_forms_fixture(root)
        walk_hits = find_git_os_walk(root)
        find_hits = find_git_find_cmd(root)
        walk_paths = paths_of(walk_hits)
        find_paths = paths_of(find_hits)
        walk_forms = {h["path"]: h["form"] for h in walk_hits}
        file_hits = [h for h in walk_hits if h["kind"] == "file"]
        dir_hits = [h for h in walk_hits if h["kind"] == "directory"]
        found_file = any(h["form"] == "submodule-gitfile" for h in file_hits)
        found_dir = any(h["form"] == "git-directory" for h in dir_hits)
        decoy_hit = any(p.endswith("/git") or p == "git" for p in walk_paths)
        agree = walk_paths == find_paths
        both = found_file and found_dir
        return {
            "walk_paths": walk_paths,
            "find_paths": find_paths,
            "walk_forms": walk_forms,
            "found_git_file": found_file,
            "found_git_directory": found_dir,
            "decoy_named_git_ignored": not decoy_hit,
            "finders_agree": agree,
            "control_pass": both and agree and not decoy_hit,
        }


def main() -> int:
    ctl = run_control()
    live = live_git_inventory(repo_root())
    out = {
        "probe": "probe1-git-file-and-directory",
        "control": ctl,
        "live": {
            "os_walk_count": live["os_walk_count"],
            "find_count": live["find_count"],
            "paths_agree": live["paths_agree"],
            "entries": live["entries"],
        },
    }
    print(json.dumps(out, sort_keys=True))
    if not ctl["control_pass"]:
        print("FAILED:AUD-0009-probe1 finder missed .git FILE or directory form, or finders disagree")
        return 1
    if not live["paths_agree"]:
        print("FAILED:AUD-0009-probe1 live os.walk and find path sets disagree")
        return 1
    print(
        "SUCCESS:AUD-0009-probe1 both-forms fixture "
        f"file={ctl['found_git_file']} dir={ctl['found_git_directory']} "
        f"live_git_entries={live['os_walk_count']}"
    )
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    raise SystemExit(main())
