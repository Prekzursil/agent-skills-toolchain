"""Locate catalog-cited 08-registry and 09-blueprint sources on this worktree."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

REGISTRY_NAME = "08-WORKFLOW-CANDIDATE-REGISTRY.json"
BLUEPRINT_NAME = "09-WORKFLOW-BLUEPRINT-LIBRARY.json"

HARNESS = "harness-restore-20260806"


def _windows_restore(name: str) -> list[Path]:
    root = Path("C:/Users/Prekzursil/.claude") / HARNESS / name
    return [
        root,
        Path("/mnt/c/Users/Prekzursil/.claude") / HARNESS / name,
        Path("/c/Users/Prekzursil/.claude") / HARNESS / name,
        Path.home() / ".claude" / HARNESS / name,
    ]


def candidate_paths(name: str) -> list[Path]:
    rels = [
        Path(name),
        Path("command-center") / name,
        Path("command-center/sources") / name,
        Path("command-center/p2-wave") / name,
        Path("command-center/wfa") / name,
    ]
    out: list[Path] = []
    for p in _windows_restore(name) + [REPO / r for r in rels]:
        if p not in out:
            out.append(p)
    return out


def first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        try:
            if p.is_file() and p.stat().st_size > 0:
                return p
        except OSError:
            continue
    return None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def looks_like_candidate_registry(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    cands = doc.get("candidates")
    if not isinstance(cands, list) or len(cands) < 20:
        return False
    sample = cands[0]
    return isinstance(sample, dict) and "id" in sample and (
        "evidence" in sample or "family" in sample
    )


def looks_like_blueprint_library(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    for key in ("blueprints", "records", "workflows", "entries"):
        rows = doc.get(key)
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            if any("bench" in r or r.get("kind") == "workflow_blueprint" for r in rows[:8]):
                return True
    return False


def find_registry_shaped(repo: Path = REPO) -> Path | None:
    named = first_existing(candidate_paths(REGISTRY_NAME))
    if named is not None:
        try:
            if looks_like_candidate_registry(load_json(named)):
                return named
        except (OSError, json.JSONDecodeError):
            pass
    extras = [
        repo / "command-center/_wfa2_entries.json",
        repo / "command-center/catalog-slices/WFA-1.json",
    ]
    for path in extras:
        try:
            if path.is_file() and looks_like_candidate_registry(load_json(path)):
                return path
        except (OSError, json.JSONDecodeError):
            continue
    return named


def find_blueprint_library(repo: Path = REPO) -> Path | None:
    return first_existing(candidate_paths(BLUEPRINT_NAME))


def source_probe(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"present": False, "path": None, "bytes": 0, "sha256": None}
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    import hashlib

    rel = path.as_posix()
    try:
        rel = path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        rel = str(path)
    return {
        "present": True,
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
