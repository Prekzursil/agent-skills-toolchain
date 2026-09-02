"""Evidence A (filesystem) and evidence B (HEAD index / git ls-tree).

A-vs-B disagreement IS the finding (live-only versus repo-only drift).
Evidence B never os.stat()s the live tree; an untracked file cannot mint a
HEAD hit.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

# Never join B to A by restating A.
# Evidence B is git ls-tree / cat-file, or the fixture head-index.


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _kind_from_path(path: Path) -> str:
    parts = [p.lower() for p in path.parts]
    name = path.name.lower()
    if "skills-a" in parts or "skills-b" in parts or name == "skill.md":
        return "skill"
    if "rules" in parts or path.suffix == ".md":
        return "rule"
    if "plugins" in parts or name == "plugin.json":
        return "plugin"
    if "workflows" in parts:
        return "workflow"
    return "other"


def scan_filesystem(roots: list[Path]) -> dict[str, dict[str, Any]]:
    """Evidence A: per-name filesystem hit with path and size."""
    hits: dict[str, dict[str, Any]] = {}
    for root in roots:
        if not root.is_dir():
            continue
        try:
            files = [p for p in root.rglob("*") if p.is_file()]
        except OSError:
            continue
        for path in files:
            try:
                digest, size = digest_file(path)
            except OSError:
                continue
            rel = path.as_posix()
            names = set(path.parts)
            names.add(path.stem)
            names.add(path.parent.name)
            for name in names:
                if not name.startswith("wfa0002-"):
                    continue
                if name.endswith(".body"):
                    name = name[: -len(".body")]
                rec = {
                    "name": name,
                    "path": rel,
                    "bytes": size,
                    "sha256": digest,
                    "kind": _kind_from_path(path),
                    "source": "filesystem",
                }
                prev = hits.get(name)
                if prev is None or rec["bytes"] > prev["bytes"]:
                    hits[name] = rec
    return hits


def load_head_index(path: Path) -> dict[str, dict[str, Any]]:
    """Evidence B fixture: independent of live untracked files."""
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries") or {}
    out: dict[str, dict[str, Any]] = {}
    for name, rec in entries.items():
        if not isinstance(rec, dict):
            continue
        out[name] = {
            "name": name,
            "path": str(rec.get("path") or ""),
            "bytes": int(rec.get("bytes") or 0),
            "sha256": str(rec.get("sha256") or ""),
            "kind": str(rec.get("kind") or "other"),
            "source": "git-HEAD",
            "repo_only": bool(rec.get("repo_only")),
        }
    return out


def git_ls_tree_lookup(repo: Path, names: list[str]) -> dict[str, dict[str, Any]]:
    """Evidence B live: git ls-tree -r HEAD; cannot see untracked files."""
    git_dir = repo / ".git"
    if not git_dir.exists():
        return {}
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "ls-tree", "-r", "--full-tree", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if proc.returncode != 0:
        return {}
    wanted = set(names)
    hits: dict[str, dict[str, Any]] = {}
    for line in proc.stdout.splitlines():
        if "\t" not in line:
            continue
        meta, rel = line.split("\t", 1)
        parts = meta.split()
        if len(parts) < 3:
            continue
        sha = parts[2]
        base = Path(rel).name
        stem = Path(rel).stem
        parent = Path(rel).parent.name
        matched = None
        for cand in (base, stem, parent, rel):
            if cand in wanted:
                matched = cand
                break
        if matched is None:
            continue
        size = 0
        try:
            sz = subprocess.run(
                ["git", "-C", str(repo), "cat-file", "-s", sha],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if sz.returncode == 0:
                size = int((sz.stdout or "0").strip() or "0")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            size = 0
        hits[matched] = {
            "name": matched,
            "path": rel,
            "bytes": size,
            "sha256": sha,
            "kind": _kind_from_path(Path(rel)),
            "source": "git-HEAD",
        }
    return hits


def evidence_b(
    names: list[str],
    head_index: dict[str, dict[str, Any]],
    repo: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """HEAD lookup. Never walks the live filesystem."""
    out = {k: v for k, v in head_index.items() if k in set(names)}
    if repo is not None:
        live = git_ls_tree_lookup(repo, names)
        for k, v in live.items():
            out[k] = v
    return out


def pair_ab(
    names: list[str],
    hits_a: dict[str, dict[str, Any]],
    hits_b: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for name in names:
        a = hits_a.get(name)
        b = hits_b.get(name)
        if bool(a) and not bool(b):
            drift: str | None = "live-only"
        elif bool(b) and not bool(a):
            drift = "repo-only"
        elif (
            a
            and b
            and a.get("sha256")
            and b.get("sha256")
            and a["sha256"] != b["sha256"]
            and a.get("bytes") != b.get("bytes")
        ):
            drift = "content-mismatch"
        else:
            drift = None
        rows.append(
            {
                "name": name,
                "A_hit": a is not None,
                "B_hit": b is not None,
                "A": a,
                "B": b,
                "drift": drift,
                "A_path": None if a is None else a.get("path"),
                "A_bytes": None if a is None else a.get("bytes"),
                "B_path": None if b is None else b.get("path"),
                "B_bytes": None if b is None else b.get("bytes"),
            }
        )
    return rows
