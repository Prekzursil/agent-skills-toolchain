

def measure_disjoint_indexes(repo, worktrees_root) -> dict:
    """Signal 1: two concurrent mutating units produce disjoint staged sets.

    Also runs the real contamination control: the same two unit files on ONE
    shared checkout plus a broad git add -A stage both paths, which is the
    measured contamination mode isolated provisioning prevents.
    """
    from pathlib import Path

    repo = Path(repo)
    root = Path(worktrees_root)
    root.mkdir(parents=True, exist_ok=True)
    a = provision_worktree(repo, "unit-a", root)
    b = provision_worktree(repo, "unit-b", root)
    shared = None
    try:
        (Path(a["path"]) / "unit-a.txt").write_text("A-mut\n", encoding="utf-8")
        (Path(b["path"]) / "unit-b.txt").write_text("B-mut\n", encoding="utf-8")
        _git(["add", "unit-a.txt"], cwd=a["path"])
        _git(["add", "unit-b.txt"], cwd=b["path"])
        staged_a = _staged(a["path"])
        staged_b = _staged(b["path"])
        inter = sorted(set(staged_a) & set(staged_b))
        idx_a, idx_b = Path(a["index_path"]), Path(b["index_path"])
        index_paths_distinct = path_key(a["gitdir"]) != path_key(b["gitdir"])
        index_bytes_differ = (
            idx_a.is_file() and idx_b.is_file() and idx_a.read_bytes() != idx_b.read_bytes()
        )
        # Real contamination control: shared checkout + broad add sweeps both.
        shared = provision_worktree(repo, "shared", root)
        (Path(shared["path"]) / "unit-a.txt").write_text("A-mut\n", encoding="utf-8")
        (Path(shared["path"]) / "unit-b.txt").write_text("B-mut\n", encoding="utf-8")
        _git(["add", "-A"], cwd=shared["path"])
        staged_shared = _staged(shared["path"])
        shared_intersection = sorted({"unit-a.txt", "unit-b.txt"} & set(staged_shared))
        contamination_detected = len(shared_intersection) == 2
        return {
            "pass": (
                not inter
                and bool(staged_a)
                and bool(staged_b)
                and index_paths_distinct
                and index_bytes_differ
                and contamination_detected
            ),
            "staged_a": staged_a,
            "staged_b": staged_b,
            "intersection": inter,
            "intersection_empty": not inter,
            "indexes_disjoint": not inter,
            "index_a": a["index_path"],
            "index_b": b["index_path"],
            "index_paths_distinct": index_paths_distinct,
            "index_bytes_differ": index_bytes_differ,
            "branches": [a["branch"], b["branch"]],
            "contamination_control": {
                "mode": "shared-checkout-broad-add",
                "staged_shared": staged_shared,
                "shared_intersection": shared_intersection,
                "detected": contamination_detected,
            },
        }
    finally:
        for prov in (a, b, shared):
            if prov is None:
                continue
            try:
                teardown_worktree(repo, prov, harvest_digests=harvest_digest(prov["path"]))
            except (RuntimeError, OSError):
                pass
