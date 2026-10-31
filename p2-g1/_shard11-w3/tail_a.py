# --------------------------------------------------------------------------
# IMP-0223: disposable per-unit worktree provision + content-gated teardown
# --------------------------------------------------------------------------
# Repair 2026-10-26 (builder shard11 wave3): the previous versions of
# measure_disjoint_indexes / measure_teardown_both_states carried two
# green-not-live defects:
#   * the contamination control compared _staged(shared) == _staged(shared),
#     a tautology that could never fail;
#   * the squash-merge teardown case was a hardcoded literal dict, and the
#     "harvested" case force-removed the worktree without any harvest check.
# Both are replaced below with computed measurements. The provision /
# teardown primitives are real functions, not probe narration.


def provision_worktree(repo, unit_id, worktrees_root, token=None):
    """Provision a disposable worktree for one file-mutating unit.

    Each unit gets its own branch (shard/<unit>/<token>) and, because every
    linked worktree owns a separate $GIT_DIR/index, its own git index -- a
    broad git add in unit A can never sweep unit B's paths.
    """
    import uuid
    from pathlib import Path

    repo = Path(repo)
    root = Path(worktrees_root)
    root.mkdir(parents=True, exist_ok=True)
    token = token or uuid.uuid4().hex[:8]
    branch = f"shard/{unit_id}/{token}"
    safe = str(unit_id).replace("/", "-")
    path = root / f"{safe}-{token}"
    _git(["worktree", "add", "-b", branch, str(path), "HEAD"], cwd=repo)
    common = git_common_dir(repo)
    gitdir, _base, err = resolve_gitdir(path, common)
    if gitdir is None:
        raise ArtifactError(f"provisioned worktree has no resolvable gitdir: {err}")
    return {
        "unit_id": unit_id,
        "token": token,
        "branch": branch,
        "path": str(path),
        "gitdir": gitdir,
        "index_path": str(Path(gitdir) / "index"),
    }


def _worktree_files(worktree_path):
    """Every live file under the worktree except the .git entry itself."""
    from pathlib import Path

    wt = Path(worktree_path)
    out = []
    for p in sorted(wt.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(wt)
        if rel.parts and rel.parts[0] == ".git":
            continue
        out.append((rel.as_posix(), p))
    return out


def harvest_digest(worktree_path):
    """Content digest of every live worktree file (CRLF-normalized)."""
    rows = {}
    for rel, p in _worktree_files(worktree_path):
        rows[rel] = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return rows


def _harvest_rows(harvest_dir):
    from pathlib import Path

    rows = {}
    hd = Path(harvest_dir)
    for p in sorted(hd.rglob("*")):
        if p.is_file():
            rows[p.relative_to(hd).as_posix()] = hashlib.sha256(
                p.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
    return rows


def teardown_worktree(repo, provisioned, harvest_dir=None, harvest_digests=None):
    """Tear down a provisioned unit worktree ONLY after content is proven.

    Authorization is byte-level comparison of every live file AND every
    index-referenced path against the harvest. Commit ancestry is never
    consulted: after a squash-merge a fully-carried branch still reports
    AHEAD, so ancestry can neither prove nor disprove preservation.
    """
    from pathlib import Path

    repo = Path(repo)
    wt = Path(provisioned["path"])
    if not wt.exists():
        return {"deleted": False, "refused": True, "reason": "worktree-absent", "missing": []}

    live = harvest_digest(wt)
    preserved = {}
    if harvest_digests is not None:
        preserved = dict(harvest_digests)
    elif harvest_dir is not None:
        preserved = _harvest_rows(harvest_dir)

    missing = sorted(rel for rel, sha in live.items() if preserved.get(rel) != sha)
    # Index-referenced paths (committed + staged) must be preserved too, so a
    # path deleted from disk but still in the index cannot silently vanish.
    rc, out, err = run_git(["ls-files"], cwd=wt)
    if rc != 0:
        return {"deleted": False, "refused": True, "reason": "index-unreadable",
                "missing": [], "detail": err.strip()}
    for rel in (ln.strip().replace("\\", "/") for ln in out.splitlines()):
        if rel and rel not in missing and rel not in preserved:
            missing.append(rel)
    missing = sorted(set(missing))
    if missing:
        return {
            "deleted": False,
            "refused": True,
            "reason": "unpreserved-content",
            "missing": missing[:20],
            "missing_count": len(missing),
            "path": str(wt),
        }

    _git(["worktree", "remove", "--force", str(wt)], cwd=repo)
    try:
        _git(["branch", "-D", provisioned["branch"]], cwd=repo)
    except RuntimeError:
        pass
    return {
        "deleted": not wt.exists(),
        "refused": False,
        "reason": "content-proven",
        "missing": [],
        "path": str(wt),
    }
