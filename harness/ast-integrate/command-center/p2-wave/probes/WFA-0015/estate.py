#!/usr/bin/env python3
"""Deterministic 20-to-6 worktree estate for WFA-0015 controls.

Synthetic ids for the 14 removed trees are CONTROL-FIXTURE labels. They are
not claimed to be the historical Windows paths.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from sweep import BlobIndex, PRESERVED, UNIQUE, classify_sha, sha256_bytes, sweep_worktrees

REMAINING = [
    "ast-integrate",
    "agent-skills-toolchain",
    "ast-harness-reconcile",
    "ast-statusline-capture",
    "cookie-bridge-skill",
    "ast-increment1",
]
NEEDS_OWNER = [
    "agent-skills-toolchain",
    "ast-harness-reconcile",
    "ast-statusline-capture",
    "cookie-bridge-skill",
    "ast-increment1",
]
REMOVED = [f"removed-wt-{i:02d}" for i in range(1, 15)]
DIRTY_COUNT = 24


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8")


def _canonical(i: int) -> str:
    return (
        f"# canonical workflow {i:02d}\n"
        f"name: canonical-flow-{i:02d}\n"
        "kind: workflow\n"
        "stages: [intake, gate, ship]\n"
    )


def _unique_dirty(i: int) -> str:
    return (
        f"# unique dirty workflow {i:02d}\n"
        f"name: toolchain-dirty-{i:02d}\n"
        "kind: workflow\n"
        "fusion: true\n"
        "orchestration stage: local-dirty\n"
        f"nonce: unique-bytes-{i:02d}-wfa0015\n"
    )


def _pr_merged(i: int) -> str:
    return (
        f"# pr-merged workflow {i:02d}\n"
        f"name: pr-merged-flow-{i:02d}\n"
        "kind: workflow\n"
        "PR-MERGED: true\n"
    )


def _fusion_unique(name: str) -> str:
    return (
        f"# fusion workflow unique to {name}\n"
        "kind: workflow\n"
        "fusion: true\n"
        "multi-stage workflow: council -> extract -> gate\n"
        f"nonce: fusion-{name}-wfa0015\n"
    )


def build_estate(root: Path) -> dict:
    """Materialise remaining trees, origin/*, PR-MERGED, and removed remnants."""
    remaining_root = root / "remaining"
    origin_root = root / "origin" / "main"
    pr_root = root / "pr-merged" / "PR-280"
    remnant_root = root / "remnants"
    ahead_root = root / "squash-ahead" / "feature-already-merged"

    for i in range(1, 9):
        _write(origin_root / "skills" / f"canonical-{i:02d}.md", _canonical(i))
    _write(
        origin_root / "skills" / "reconcile.md",
        "# reconcile\nkind: workflow\nstages: [diff, apply]\n",
    )
    _write(
        origin_root / "skills" / "cookie-bridge.md",
        "# cookie-bridge\nkind: workflow\nstages: [read, write]\n",
    )
    _write(
        origin_root / ".github" / "workflows" / "gate.yml",
        "name: gate\non: [push]\njobs: {gate: {runs-on: linux}}\n",
    )

    for i in range(9, 13):
        _write(pr_root / "skills" / f"pr-{i:02d}.md", _pr_merged(i))

    # Main remaining tree: origin-identical workflows (clean).
    main = remaining_root / "ast-integrate"
    for i in range(1, 9):
        _write(main / "skills" / f"canonical-{i:02d}.md", _canonical(i))
    _write(main / ".github" / "workflows" / "gate.yml", (origin_root / ".github" / "workflows" / "gate.yml").read_text(encoding="utf-8"))
    _write(main / "docs" / "notes.txt", "not a workflow\n")

    # agent-skills-toolchain: 24 dirty workflow files, classified individually.
    tool = remaining_root / "agent-skills-toolchain"
    dirty: set[str] = set()
    for i in range(1, 9):
        rel = f"skills/dirty-{i:02d}.md"
        _write(tool / rel, _canonical(i))  # same bytes as origin, different path
        dirty.add(rel)
    for i in range(9, 13):
        rel = f"skills/dirty-{i:02d}.md"
        _write(tool / rel, _pr_merged(i))
        dirty.add(rel)
    for i in range(13, 25):
        rel = f"skills/dirty-{i:02d}.md"
        _write(tool / rel, _unique_dirty(i))
        dirty.add(rel)
    _write(tool / "README.md", "agent-skills-toolchain working tree\n")

    rec = remaining_root / "ast-harness-reconcile"
    _write(rec / "skills" / "reconcile.md", (origin_root / "skills" / "reconcile.md").read_text(encoding="utf-8"))

    cap = remaining_root / "ast-statusline-capture"
    _write(cap / "skills" / "statusline-fusion.md", _fusion_unique("ast-statusline-capture"))

    cookie = remaining_root / "cookie-bridge-skill"
    _write(
        cookie / "skills" / "cookie-bridge.md",
        (origin_root / "skills" / "cookie-bridge.md").read_text(encoding="utf-8"),
    )

    inc = remaining_root / "ast-increment1"
    _write(inc / "skills" / "increment-fusion.md", _fusion_unique("ast-increment1"))

    # Squash-merged branch that git ancestry would report as ahead: bytes == origin.
    for i in range(1, 9):
        _write(ahead_root / "skills" / f"canonical-{i:02d}.md", _canonical(i))
    _write(
        ahead_root / ".github" / "workflows" / "gate.yml",
        (origin_root / ".github" / "workflows" / "gate.yml").read_text(encoding="utf-8"),
    )

    # 14 removed remnants: 10 preserved on origin, 4 unique.
    for i, name in enumerate(REMOVED, start=1):
        tree = remnant_root / name
        if i <= 10:
            _write(tree / "skills" / "canonical-01.md", _canonical(1))
        else:
            _write(tree / "skills" / "lost-fusion.md", _fusion_unique(name))

    origin_index = BlobIndex()
    origin_index.ingest_tree(origin_root, "origin/main")
    origin_index.ingest_tree(pr_root, "pr-merged/PR-280")

    trees = {name: remaining_root / name for name in REMAINING}
    dirty_paths = {"agent-skills-toolchain": dirty}
    rows = sweep_worktrees(trees, origin_index, dirty_paths)

    remnant_rows = []
    for name in REMOVED:
        for rel, data in _iter(remnant_root / name):
            digest = sha256_bytes(data)
            klass, locs = classify_sha(digest, origin_index)
            remnant_rows.append(
                {
                    "worktree": name,
                    "relpath": rel,
                    "sha256": digest,
                    "classification": klass,
                    "preserved_at": locs,
                    "source": "fixture-remnant",
                }
            )

    ahead_rows = []
    for rel, data in _iter(ahead_root):
        digest = sha256_bytes(data)
        klass, locs = classify_sha(digest, origin_index)
        ahead_rows.append(
            {
                "relpath": rel,
                "sha256": digest,
                "classification": klass,
                "preserved_at": locs,
                "ancestry_would_say": "ahead-of-main",
            }
        )

    worktree_names_before = sorted(trees.keys())
    worktree_names_after = sorted(p.name for p in remaining_root.iterdir() if p.is_dir())

    return {
        "root": str(root),
        "remaining": list(REMAINING),
        "needs_owner": list(NEEDS_OWNER),
        "removed_fixture_ids": list(REMOVED),
        "trees": {k: str(v) for k, v in trees.items()},
        "origin_index": origin_index,
        "rows": rows,
        "dirty_paths": {k: sorted(v) for k, v in dirty_paths.items()},
        "remnant_rows": remnant_rows,
        "ahead_rows": ahead_rows,
        "worktree_names_before": worktree_names_before,
        "worktree_names_after": worktree_names_after,
        "deletions_performed": [],
        "ahead_root": str(ahead_root),
        "origin_root": str(origin_root),
        "pr_root": str(pr_root),
        "remnant_root": str(remnant_root),
    }


def _iter(root: Path):
    if not root.is_dir():
        return
    from sweep import iter_files

    yield from iter_files(root)


def both_states_unique_then_preserve(root: Path) -> dict:
    """Plant a file that exists only in one worktree, then copy bytes onto origin."""
    estate = build_estate(root)
    tool = Path(estate["trees"]["agent-skills-toolchain"])
    planted_rel = "skills/planted-only.md"
    planted = (
        "# planted unique workflow\n"
        "kind: workflow\n"
        "fusion: true\n"
        "nonce: planted-only-wfa0015\n"
    )
    _write(tool / planted_rel, planted)
    digest = sha256_bytes(planted.encode("utf-8"))
    index: BlobIndex = estate["origin_index"]
    before_class, before_locs = classify_sha(digest, index)
    origin_copy = Path(estate["origin_root"]) / "skills" / "planted-copy.md"
    _write(origin_copy, planted)
    index.add(digest, "origin/main:skills/planted-copy.md")
    after_class, after_locs = classify_sha(digest, index)
    return {
        "digest": digest,
        "before_class": before_class,
        "before_locs": before_locs,
        "after_class": after_class,
        "after_locs": after_locs,
        "want_before": UNIQUE,
        "want_after": PRESERVED,
        "pass": before_class == UNIQUE
        and not before_locs
        and after_class == PRESERVED
        and after_locs == ["origin/main:skills/planted-copy.md"],
    }
