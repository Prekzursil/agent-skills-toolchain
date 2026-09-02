"""Locate 08-WORKFLOW-CANDIDATE-REGISTRY.json without inventing a 284-row file."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTRY_NAME = "08-WORKFLOW-CANDIDATE-REGISTRY.json"
HARNESS = "harness-restore-20260806"
EXPECTED_N = 284


def _windows_restore(name: str) -> list[Path]:
    root = Path("C:/Users/Prekzursil/.claude") / HARNESS / name
    return [
        root,
        Path("/mnt/c/Users/Prekzursil/.claude") / HARNESS / name,
        Path("/c/Users/Prekzursil/.claude") / HARNESS / name,
        Path.home() / ".claude" / HARNESS / name,
    ]


def candidate_paths(name: str = REGISTRY_NAME) -> list[Path]:
    rels = [
        Path(name),
        Path("command-center") / name,
        Path("command-center/sources") / name,
        Path("command-center/p2-wave") / name,
        Path("command-center/wfa") / name,
        Path("command-center/p2-wave/probes/WFA-0005") / name,
    ]
    out: list[Path] = []
    for p in _windows_restore(name) + [REPO / r for r in rels]:
        if p not in out:
            out.append(p)
    return out


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def candidates_of(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("candidates", "records", "entries"):
        rows = doc.get(key)
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def looks_like_classified_registry(doc: Any) -> bool:
    """Require classification on rows. WFA-0032 reconstructions do not qualify."""
    rows = candidates_of(doc)
    if len(rows) < 20:
        return False
    classified = sum(1 for r in rows if r.get("classification"))
    return classified >= 20


def first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        try:
            if p.is_file() and p.stat().st_size > 0:
                return p
        except OSError:
            continue
    return None


def find_registry(repo: Path = REPO) -> Path | None:
    named = first_existing(candidate_paths())
    if named is not None:
        try:
            if looks_like_classified_registry(load_json(named)):
                return named
        except (OSError, json.JSONDecodeError):
            pass
    extras = [
        repo / "command-center/_wfa2_entries.json",
        repo / "command-center/catalog-slices/WFA-1.json",
    ]
    for path in extras:
        try:
            if path.is_file() and looks_like_classified_registry(load_json(path)):
                return path
        except (OSError, json.JSONDecodeError):
            continue
    return None


def relpath(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def source_probe(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "present": False,
            "path": None,
            "bytes": 0,
            "sha256": None,
            "n_candidates": 0,
        }
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    doc = json.loads(raw.decode("utf-8"))
    return {
        "present": True,
        "path": relpath(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "n_candidates": len(candidates_of(doc)),
    }


def live_registry(repo: Path = REPO) -> dict[str, Any]:
    path = find_registry(repo)
    probe = source_probe(path)
    doc = load_json(path) if path is not None else None
    rows = candidates_of(doc) if doc is not None else []
    vocab = []
    counts_block = {}
    if isinstance(doc, dict):
        raw_vocab = doc.get("classification_vocabulary")
        if isinstance(raw_vocab, list):
            vocab = [str(v) for v in raw_vocab]
        elif isinstance(raw_vocab, dict):
            vocab = [str(k) for k in raw_vocab.keys()]
        raw_counts = doc.get("counts")
        if isinstance(raw_counts, dict):
            counts_block = {
                str(k): int(v)
                for k, v in raw_counts.items()
                if isinstance(v, int) or (isinstance(v, str) and str(v).isdigit())
            }
    return {
        "source": probe,
        "doc": doc,
        "candidates": rows,
        "vocabulary_declared": vocab,
        "counts_block": counts_block,
        "catalog_expected_n": EXPECTED_N,
    }
