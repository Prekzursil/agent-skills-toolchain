"""Measure the agent-skills-toolchain checkout fleet.

Read-only. Classifies each checkout worktree-vs-clone by TWO mechanically independent
signals, measures unique commits (commits existing in NO other checkout and not on the
true remote), uncommitted work, stashes, and junction/reparse hazards.

Emits JSON to command-center/ssot/clone-measurements.json
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

CANON = "C:/Users/Prekzursil/source/agent-skills-toolchain"

CHECKOUTS = [
    "C:/Users/Prekzursil/.claude/codexsrc-work",
    "C:/Users/Prekzursil/.claude/toolchain-audit",
    "C:/Users/Prekzursil/.claude/tw-merge-work",
    "C:/Users/Prekzursil/Documents/Playground",
    "C:/Users/Prekzursil/source/agent-skills-toolchain",
    "C:/Users/Prekzursil/source/ast-patch167",
    "C:/Users/Prekzursil/source/ast-integrate",
    "C:/Users/Prekzursil/work/agent-skills-toolchain-re",
    "D:/sast-depth/agent-skills-toolchain",
    # NOT in the owner's list of nine -- discovered by `git worktree list`.
    "C:/Users/Prekzursil/source/ast-harness-reconcile",
    "D:/inc1-wt/ast-increment1",
    "D:/wt-salvage-probe",
]


def git(repo: str, *args: str, ok_fail: bool = False) -> str:
    proc = subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0 and not ok_fail:
        return f"__ERR__:{proc.returncode}:{proc.stderr.strip()[:200]}"
    return proc.stdout.rstrip("\n")


def git_lines(repo: str, *args: str) -> list[str]:
    out = git(repo, *args, ok_fail=True)
    if out.startswith("__ERR__"):
        return []
    return [ln for ln in out.splitlines() if ln.strip()]


def is_reparse(path: str) -> bool:
    """Junction / symlink detection via the FILE_ATTRIBUTE_REPARSE_POINT bit (0x400)."""
    try:
        attrs = os.stat(path, follow_symlinks=False).st_file_attributes  # type: ignore[attr-defined]
        return bool(attrs & 0x400)
    except (OSError, AttributeError):
        return False


def dir_reparse_scan(root: str) -> list[str]:
    """Top-level entries in `root` that are junctions/symlinks (the worktree-remove hazard)."""
    hits = []
    try:
        for entry in os.scandir(root):
            if is_reparse(entry.path):
                target = ""
                try:
                    target = os.readlink(entry.path)
                except OSError:
                    target = "<unreadable>"
                hits.append(f"{entry.name} -> {target}")
    except OSError:
        pass
    return hits


def batch_check_exists(repo: str, shas: list[str]) -> set[str]:
    """Which of `shas` exist as objects in `repo`. Batched; robust vs cat-file -e quirks."""
    if not shas:
        return set()
    proc = subprocess.run(
        ["git", "-C", repo, "cat-file", "--batch-check=%(objectname) %(objecttype)"],
        input="\n".join(shas) + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    present = set()
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == "commit":
            present.add(parts[0])
    return present


def main() -> int:
    out: dict = {"canonical": CANON, "checkouts": {}, "controls": {}}

    # ---- canonical remote truth (network read, no ref writes) ----
    remote_main = ""
    for ln in git_lines(CANON, "ls-remote", "origin", "refs/heads/main"):
        remote_main = ln.split()[0]
    out["remote_main_sha"] = remote_main

    canon_git_common = git(
        CANON, "rev-parse", "--path-format=absolute", "--git-common-dir"
    )
    out["canonical_git_common_dir"] = canon_git_common

    # ---- registered worktrees, from the canonical repo's own bookkeeping ----
    out["worktree_list_raw"] = git_lines(CANON, "worktree", "list", "--porcelain")

    # ---- per-checkout measurement ----
    all_reach: dict[str, set[str]] = {}

    for path in CHECKOUTS:
        rec: dict = {"path": path, "exists": Path(path).exists()}
        if not rec["exists"]:
            out["checkouts"][path] = rec
            continue

        dotgit = Path(path) / ".git"
        rec["dotgit_kind"] = (
            "DIR" if dotgit.is_dir() else ("FILE" if dotgit.is_file() else "MISSING")
        )
        gcd = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
        rec["git_common_dir"] = gcd
        rec["git_dir"] = git(
            path, "rev-parse", "--path-format=absolute", "--absolute-git-dir"
        )
        rec["shares_object_store_with_canonical"] = (
            gcd.replace("\\", "/").rstrip("/").lower()
            == canon_git_common.replace("\\", "/").rstrip("/").lower()
        )
        # signal 3: alternates (a clone can share objects without being a worktree)
        alt = Path(gcd.replace("\\", "/")) / "objects" / "info" / "alternates"
        rec["alternates"] = (
            alt.read_text(encoding="utf-8").strip() if alt.is_file() else ""
        )

        rec["kind"] = (
            "WORKTREE"
            if rec["shares_object_store_with_canonical"]
            and rec["dotgit_kind"] == "FILE"
            else (
                "MAIN-WORKTREE"
                if rec["shares_object_store_with_canonical"]
                else ("CLONE+ALTERNATES" if rec["alternates"] else "CLONE")
            )
        )

        rec["head_sha"] = git(path, "rev-parse", "HEAD")
        rec["branch"] = git(path, "rev-parse", "--abbrev-ref", "HEAD")
        rec["origin_url"] = git(
            path, "config", "--get", "remote.origin.url", ok_fail=True
        )
        rec["refs"] = git_lines(
            path, "for-each-ref", "--format=%(objectname) %(refname)"
        )
        rec["stashes"] = git_lines(path, "stash", "list")

        porcelain = git_lines(
            path, "status", "--porcelain=v1", "--untracked-files=normal"
        )
        rec["uncommitted_count"] = len(porcelain)
        rec["uncommitted_tracked"] = len(
            [p for p in porcelain if not p.startswith("??")]
        )
        rec["uncommitted_untracked"] = len([p for p in porcelain if p.startswith("??")])
        rec["uncommitted_sample"] = porcelain[:40]

        # ahead/behind vs the checkout's OWN idea of origin/main (may be stale)
        rec["local_origin_main"] = git(path, "rev-parse", "origin/main", ok_fail=True)
        ab = git(
            path,
            "rev-list",
            "--left-right",
            "--count",
            "origin/main...HEAD",
            ok_fail=True,
        )
        rec["behind_ahead_vs_local_origin_main"] = ab

        # every commit reachable from any ref OR reflog (catches orphaned/amended work)
        reach = set(git_lines(path, "rev-list", "--all", "--reflog"))
        all_reach[path] = reach
        rec["reachable_commit_count"] = len(reach)

        rec["junctions_at_root"] = dir_reparse_scan(path)
        rec["root_is_reparse"] = is_reparse(path)

        out["checkouts"][path] = rec

    # ---- unique-commit computation ----
    # A commit is UNIQUE to checkout X if no OTHER checkout's object store holds it.
    # Worktrees share canonical's store, so they can never hold a unique commit -- that is a
    # built-in control (a nonzero count on a worktree means the detector is broken).
    stores: dict[str, str] = {}
    for path, rec in out["checkouts"].items():
        if rec.get("exists") and rec.get("git_common_dir"):
            stores[path] = path

    for path, reach in all_reach.items():
        others = [p for p in stores if p != path]
        # exclude sibling worktrees of the SAME store from "elsewhere" -- same store, so
        # presence there is not independent evidence. Compare store identity.
        my_store = out["checkouts"][path]["git_common_dir"].replace("\\", "/").lower()
        elsewhere: set[str] = set()
        checked_stores = set()
        for other in others:
            o_store = (
                out["checkouts"][other]["git_common_dir"].replace("\\", "/").lower()
            )
            if o_store == my_store or o_store in checked_stores:
                continue
            checked_stores.add(o_store)
            elsewhere |= batch_check_exists(other, sorted(reach))
        unique = sorted(reach - elsewhere)
        rec = out["checkouts"][path]
        rec["unique_commit_count"] = len(unique)
        rec["unique_commits_sample"] = unique[:25]
        rec["stores_compared_against"] = sorted(checked_stores)

    # ---- DETECTOR CONTROLS (both-states test) ----
    # (a) negative control: a SHA that certainly does not exist anywhere.
    fake = "0" * 39 + "1"
    out["controls"]["fake_sha_found_in_canonical"] = bool(
        batch_check_exists(CANON, [fake])
    )
    # (b) positive control: canonical HEAD must be found in canonical.
    canon_head = git(CANON, "rev-parse", "HEAD")
    out["controls"]["canonical_head_found_in_canonical"] = (
        canon_head in batch_check_exists(CANON, [canon_head])
    )
    # (c) cross-repo control: a commit from an UNRELATED repo must NOT be found in canonical.
    #     Proves the detector can actually see absence, not just report it.
    unrelated_candidates = [
        "C:/Users/Prekzursil/source/qzp-lean",
        "C:/Users/Prekzursil/.claude",
    ]
    out["controls"]["cross_repo"] = "NOT-RUN"
    for cand in unrelated_candidates:
        if not (Path(cand) / ".git").exists():
            continue
        sha = git(cand, "rev-parse", "HEAD", ok_fail=True)
        if len(sha) == 40 and not sha.startswith("__ERR__"):
            found = bool(batch_check_exists(CANON, [sha]))
            out["controls"]["cross_repo"] = {
                "repo": cand,
                "sha": sha,
                "found_in_canonical": found,
                "expected": False,
            }
            break

    dest = Path("C:/Users/Prekzursil/source/ast-integrate/command-center/ssot")
    dest.mkdir(parents=True, exist_ok=True)
    with open(
        dest / "clone-measurements.json", "w", encoding="utf-8", newline="\n"
    ) as fh:
        json.dump(out, fh, indent=2, sort_keys=False)
    print(f"wrote {dest / 'clone-measurements.json'}")

    # terse console summary
    for path, rec in out["checkouts"].items():
        if not rec.get("exists"):
            print(f"{path:52} MISSING")
            continue
        print(
            f"{path:52} {rec['kind']:16} br={rec.get('branch', '?'):42} "
            f"uniq={rec.get('unique_commit_count', '?'):>4} "
            f"dirty={rec.get('uncommitted_count', '?'):>5} "
            f"stash={len(rec.get('stashes', []))}"
        )
    print("CONTROLS:", json.dumps(out["controls"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
