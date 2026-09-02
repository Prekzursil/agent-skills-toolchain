"""Pass 2 - decompose the 'unique commit' counts.

A commit being absent from other LOCAL stores does not mean the work is at risk:
  (a) it may be pushed to origin (safe on the remote), and
  (b) its TREE may be byte-identical to a tree canonical already holds (rebase/cherry-pick),
      in which case the CONTENT is not unique even though the commit SHA is.

Also decomposes the shared canonical store's unique set against the true remote ref list.
Read-only: uses ls-remote (no fetch, no ref writes).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

CANON = "C:/Users/Prekzursil/source/agent-skills-toolchain"
SSOT = Path("C:/Users/Prekzursil/source/ast-integrate/command-center/ssot")


def git(repo: str, *args: str) -> str:
    p = subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (
        p.stdout.rstrip("\n")
        if p.returncode == 0
        else f"__ERR__:{p.stderr.strip()[:160]}"
    )


def lines(repo: str, *args: str) -> list[str]:
    o = git(repo, *args)
    return [] if o.startswith("__ERR__") else [x for x in o.splitlines() if x.strip()]


def batch_types(repo: str, objs: list[str]) -> dict[str, str]:
    if not objs:
        return {}
    p = subprocess.run(
        ["git", "-C", repo, "cat-file", "--batch-check=%(objectname) %(objecttype)"],
        input="\n".join(objs) + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    res = {}
    for ln in p.stdout.splitlines():
        parts = ln.split()
        if len(parts) == 2:
            res[parts[0]] = parts[1]
    return res


def main() -> None:
    data = json.loads((SSOT / "clone-measurements.json").read_text(encoding="utf-8"))
    out: dict = {}

    # ---- true remote ref list (network read only) ----
    remote_refs: dict[str, str] = {}
    for ln in lines(CANON, "ls-remote", "origin"):
        parts = ln.split()
        if len(parts) == 2:
            remote_refs[parts[1]] = parts[0]
    out["remote_ref_count"] = len(remote_refs)
    out["remote_refs"] = remote_refs

    # remote tips that the canonical store actually holds -> usable as --not bases
    tips_local = [
        sha
        for sha, t in batch_types(CANON, sorted(set(remote_refs.values()))).items()
        if t == "commit"
    ]
    out["remote_tips_present_in_canonical"] = len(tips_local)
    out["remote_tips_total"] = len(set(remote_refs.values()))

    # ---- shared-store decomposition: what is NOT on the remote ----
    not_pushed = lines(CANON, "rev-list", "--all", "--reflog", "--not", *tips_local)
    out["canonical_commits_not_reachable_from_any_remote_tip"] = len(not_pushed)

    # which local refs carry them
    per_ref = {}
    for ln in lines(CANON, "for-each-ref", "--format=%(objectname) %(refname)"):
        sha, ref = ln.split(maxsplit=1)
        if ref.startswith("refs/remotes/"):
            continue
        ahead = lines(CANON, "rev-list", "--count", ref, "--not", *tips_local)
        per_ref[ref] = {
            "sha": sha,
            "commits_not_on_remote": int(ahead[0]) if ahead else -1,
        }
    out["canonical_local_refs_vs_remote"] = per_ref

    # ---- per independent clone: are its unique commits remote-safe / content-duplicated? ----
    clone_detail = {}
    for path, rec in data["checkouts"].items():
        if not rec.get("exists") or rec.get("unique_commit_count", 0) == 0:
            continue
        if rec["kind"] in ("WORKTREE", "MAIN-WORKTREE"):
            continue  # handled by the shared-store decomposition above
        uniq = rec["unique_commits_sample"]
        det = {"branch": rec["branch"], "head": rec["head_sha"], "commits": []}
        # trees of those commits, checked for existence in canonical (content-level dedupe)
        for c in uniq:
            tree = git(path, "rev-parse", f"{c}^{{tree}}")
            subj = git(path, "log", "-1", "--format=%h %ad %an %s", "--date=short", c)
            tree_in_canon = batch_types(CANON, [tree]).get(tree, "MISSING")
            on_remote = any(v == c for v in remote_refs.values())
            det["commits"].append(
                {
                    "sha": c,
                    "subject": subj,
                    "tree": tree,
                    "tree_present_in_canonical": tree_in_canon,
                    "sha_is_a_remote_ref_tip": on_remote,
                }
            )
        # does the remote carry a branch of the same name?
        rb = f"refs/heads/{rec['branch']}"
        det["remote_branch_same_name"] = remote_refs.get(rb, "ABSENT")
        # how far is this clone's HEAD from the remote main
        det["merge_base_with_remote_main_present"] = batch_types(
            path, [data["remote_main_sha"]]
        ).get(data["remote_main_sha"], "MISSING")
        clone_detail[path] = det
    out["clone_unique_detail"] = clone_detail

    # ---- uncommitted work: is it ignored junk or real? ----
    dirty = {}
    for path, rec in data["checkouts"].items():
        if not rec.get("exists") or rec.get("uncommitted_count", 0) == 0:
            continue
        dirty[path] = {
            "count": rec["uncommitted_count"],
            "tracked": rec["uncommitted_tracked"],
            "untracked": rec["uncommitted_untracked"],
            "sample": rec["uncommitted_sample"],
        }
    out["dirty_detail"] = dirty

    with open(SSOT / "unique-depth.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=2)
    print(f"remote refs: {out['remote_ref_count']}")
    print(
        f"remote tips present locally: {out['remote_tips_present_in_canonical']}/{out['remote_tips_total']}"
    )
    print(
        f"canonical commits NOT on any remote tip: {out['canonical_commits_not_reachable_from_any_remote_tip']}"
    )
    for ref, v in per_ref.items():
        if v["commits_not_on_remote"] > 0:
            print(f"  {ref:60} +{v['commits_not_on_remote']}")
    for p, d in clone_detail.items():
        print(
            f"\n{p}  [{d['branch']}] remote-branch={d['remote_branch_same_name'][:12]}"
        )
        for c in d["commits"]:
            print(
                f"   {c['subject'][:96]:96} tree_in_canon={c['tree_present_in_canonical']}"
            )


if __name__ == "__main__":
    main()
