#!/usr/bin/env python3
"""Adopt already-deployed unpackaged trees in place (no wipe-and-reinstall)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from estate import (
    CLAIM_MAP,
    PRESERVE_RELS,
    REAL_PKG,
    REAL_TREE,
    SOURCE_MAP,
    SOURCE_ONLY_RELS,
    UNCLAIM_CLASS,
    UNCLAIM_WHY,
    lf_bytes,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(lf_bytes(data)).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = lf_bytes(path.read_bytes())
    return sha256_bytes(raw), len(raw)


def walk_files(root: Path) -> list[str]:
    rels: list[str] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel == "estate-meta.json":
            continue
        rels.append(rel)
    return rels


def adopt_estate(root: Path) -> dict[str, Any]:
    """Produce package manifests that claim existing live files without rewriting them."""
    packages: dict[str, dict[str, Any]] = {}
    claimed_rows: list[dict[str, Any]] = []
    unclaimed: list[dict[str, Any]] = []

    for rel in walk_files(root):
        path = root / rel
        digest, size = sha256_file(path)
        if rel in CLAIM_MAP:
            pkg_id = CLAIM_MAP[rel]
            rec = {
                "path": rel,
                "sha256": digest,
                "claimed": True,
                "bytes_rewritten": False,
                "bytes": size,
            }
            pkg = packages.setdefault(
                pkg_id,
                {
                    "id": pkg_id,
                    "version": "1.0.0",
                    "source_tree": (
                        "skills-repo/" if pkg_id == "pkg.skill.council" else rel.split("/")[0] + "/"
                    ),
                    "install_tree": rel.split("/")[0] + "/",
                    "files": [],
                },
            )
            if pkg_id == "pkg.skill.council":
                pkg["source_tree"] = "skills-repo/"
                pkg["install_tree"] = "skills-live/"
            pkg["files"].append(rec)
            claimed_rows.append(
                {
                    **rec,
                    "package_id": pkg_id,
                    "reason": "already-deployed unpackaged file adopted in place; bytes unchanged",
                }
            )
            continue
        why = UNCLAIM_WHY.get(rel)
        cls = UNCLAIM_CLASS.get(rel)
        if rel in SOURCE_MAP:
            why = why or UNCLAIM_WHY[rel]
            cls = cls or UNCLAIM_CLASS[rel]
        if why is None:
            why = "outside package boundary; not claimed"
            cls = "unknown"
        unclaimed.append({"path": rel, "why": why, "class": cls})

    expected_unclaimed = set(SOURCE_ONLY_RELS) | set(PRESERVE_RELS)
    got_unclaimed = {u["path"] for u in unclaimed}
    missing = sorted(expected_unclaimed - got_unclaimed)
    extra_claimed = sorted(set(CLAIM_MAP) - {r["path"] for r in claimed_rows})
    return {
        "packages": [packages[k] for k in sorted(packages)],
        "sample": claimed_rows,
        "unclaimed": unclaimed,
        "missing_unclaimed": missing,
        "missing_claimed": extra_claimed,
        "rewrite_live_bytes": False,
    }


def adopt_real_tree(repo: Path) -> dict[str, Any]:
    """Demonstrate adoption on one real tree on this worktree (tools/command-center)."""
    root = repo / REAL_TREE
    claimed: list[str] = []
    unclaimed: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        rel = path.relative_to(root).as_posix()
        repo_rel = f"{REAL_TREE}/{rel}"
        digest, size = sha256_file(path)
        if "/" not in rel and rel.endswith(".py"):
            claimed.append(repo_rel)
            files.append(
                {
                    "path": repo_rel,
                    "sha256": digest,
                    "claimed": True,
                    "bytes_rewritten": False,
                    "bytes": size,
                }
            )
            continue
        if rel.startswith("tests/"):
            unclaimed.append(
                {
                    "path": repo_rel,
                    "why": (
                        "dev-only test suite; not part of the lockfile-pinned runtime package"
                    ),
                    "class": "dev-tests",
                }
            )
            continue
        unclaimed.append(
            {
                "path": repo_rel,
                "why": "outside the top-level runtime-module package boundary",
                "class": "outside-boundary",
            }
        )
    return {
        "tree": REAL_TREE,
        "package_id": REAL_PKG,
        "claimed": claimed,
        "unclaimed": unclaimed,
        "files": files,
        "rewrite_live_bytes": False,
    }
