

def measure_teardown_both_states(repo, worktrees_root) -> dict:
    """Signal 2: teardown of an unpreserved worktree is refused; a harvested
    one is deleted; and on the squash-merge state the naive ancestry mutant
    authorizes while the content gate refuses - all computed, none asserted.
    """
    import shutil
    from pathlib import Path

    repo = Path(repo)
    root = Path(worktrees_root)
    root.mkdir(parents=True, exist_ok=True)

    # (1) unharvested unique remainder must refuse and stay on disk
    danger = provision_worktree(repo, "danger", root)
    dpath = Path(danger["path"])
    (dpath / "uncommitted.txt").write_text("remainder\n", encoding="utf-8")
    ref_danger = teardown_worktree(repo, danger, harvest_dir=None)
    dangerous = {
        "refused": bool(ref_danger["refused"]),
        "deleted": bool(ref_danger["deleted"]),
        "reason": ref_danger.get("reason"),
        "worktree_still_on_disk": dpath.exists(),
    }

    # (2) squash-merge: content IS carried, ancestry reports AHEAD; the naive
    # mutant authorizes deletion while the uncommitted remainder is unique.
    squash = provision_worktree(repo, "squash", root)
    spath = Path(squash["path"])
    (spath / "feature.txt").write_text("feature\n", encoding="utf-8")
    _git(["add", "feature.txt"], cwd=spath)
    _git(["commit", "-m", "shard feature"], cwd=spath)
    _git(["merge", "--squash", squash["branch"]], cwd=repo)
    _git(["commit", "-m", "integration squash"], cwd=repo)
    naive = naive_ancestry_authorizes(repo, squash["branch"])
    (spath / "uncommitted.txt").write_text("remainder\n", encoding="utf-8")
    ref_squash = teardown_worktree(repo, squash, harvest_dir=None)
    squash_res = {
        "refused": bool(ref_squash["refused"]),
        "deleted": bool(ref_squash["deleted"]),
        "reason": ref_squash.get("reason"),
        "reports_ahead": naive["reports_ahead"],
        "ahead_count": naive["ahead_count"],
        "merged_check_false_despite_content_carried": naive["merged"] is False,
        "naive_ancestry_would_authorize": bool(naive["authorize"]),
        "worktree_still_on_disk": spath.exists(),
    }

    # (3) content-proven harvest authorizes deletion
    good = provision_worktree(repo, "good", root)
    gpath = Path(good["path"])
    (gpath / "kept.txt").write_text("kept\n", encoding="utf-8")
    hdir = Path(str(gpath) + "-harvest")
    shutil.copytree(gpath, hdir, ignore=shutil.ignore_patterns(".git"))
    ref_good = teardown_worktree(repo, good, harvest_dir=hdir)
    good_res = {
        "refused": bool(ref_good["refused"]),
        "deleted": bool(ref_good["deleted"]),
        "reason": ref_good.get("reason"),
    }
    shutil.rmtree(hdir, ignore_errors=True)

    # best-effort fixture cleanup through the same content gate
    for prov, p in ((danger, dpath), (squash, spath)):
        if p.exists():
            try:
                teardown_worktree(repo, prov, harvest_digests=harvest_digest(p))
            except (RuntimeError, OSError):
                pass

    return {
        "pass": (
            dangerous["refused"]
            and dangerous["worktree_still_on_disk"]
            and not dangerous["deleted"]
            and squash_res["refused"]
            and squash_res["worktree_still_on_disk"]
            and squash_res["reports_ahead"]
            and squash_res["naive_ancestry_would_authorize"]
            and good_res["deleted"]
            and not good_res["refused"]
        ),
        "dangerous": dangerous,
        "squash_unharvested": squash_res,
        "good": good_res,
    }


if __name__ == "__main__":
    sys.exit(main())
