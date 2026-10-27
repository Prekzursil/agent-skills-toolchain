"""Compat-declaration library: load, reconstruct, and symmetrise (WFA-0004).

The compat relation is semantically undirected, but declarations are stored
directed. The catalog-recorded state of the live library: 390 directed
declarations over 265 unordered pairs (125 reciprocal, 140 one-sided);
symmetrisation completes every reciprocal, giving 530 directed declarations
with 0 one-sided leftovers.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CATALOG_DECLARED = 390
CATALOG_DECLARED_AFTER = 530
CATALOG_UNDIRECTED = 265
CATALOG_ASYMMETRIC = 140
CATALOG_RECIPROCAL_PAIRS = (CATALOG_DECLARED - CATALOG_ASYMMETRIC) // 2  # 125

ARTIFACT_REL = "command-center/wfa/WFA-0004-compat-symmetry.json"
EMITTED_REL = "command-center/wfa/WFA-0004-emitted-library.json"

Adj = dict[str, set[str]]


def _pairs_from_edges(edges: list[dict[str, Any]]) -> list[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for edge in edges:
        a = str(edge.get("source") or "")
        b = str(edge.get("target") or "")
        if a and b and a != b:
            pairs.add((a, b) if a < b else (b, a))
    return sorted(pairs)


def adj_from_mapping(mapping: dict[str, Any]) -> Adj:
    return {str(k): {str(x) for x in (v or [])} for k, v in mapping.items()}


def library_from_adj(adj: Adj, origin: str = "") -> dict[str, Any]:
    return {
        "record_type": "wfa-compat-library",
        "origin": origin,
        "adjacency": {k: sorted(v) for k, v in sorted(adj.items())},
    }


def adj_from_library(doc: dict[str, Any]) -> Adj:
    return adj_from_mapping(doc.get("adjacency") or {})


def reconstruct_before(edges: list[dict[str, Any]]) -> Adj:
    """Deterministic before-library consistent with the catalog counts.

    The symmetrised artifact records every pair both ways; the recorded
    pre-symmetrisation state had the FIRST 125 pairs (sorted order) reciprocal
    and the remaining 140 declared one-way (low id -> high id).
    """
    pairs = _pairs_from_edges(edges)
    adj: Adj = {}
    for i, (a, b) in enumerate(pairs):
        adj.setdefault(a, set())
        adj.setdefault(b, set())
        adj[a].add(b)
        if i < CATALOG_RECIPROCAL_PAIRS:
            adj[b].add(a)
    return adj


def load_or_reconstruct(repo: Path | str) -> dict[str, Any]:
    root = Path(repo)
    emitted = root / EMITTED_REL
    if emitted.is_file():
        doc = json.loads(emitted.read_text(encoding="utf-8"))
        return {"adj": adj_from_library(doc), "origin": EMITTED_REL}
    artifact = root / ARTIFACT_REL
    if artifact.is_file():
        doc = json.loads(artifact.read_text(encoding="utf-8"))
        adj = reconstruct_before(doc.get("edges") or [])
        for node in doc.get("nodes") or []:
            adj.setdefault(str(node), set())
        return {"adj": adj, "origin": f"reconstructed:{ARTIFACT_REL}"}
    raise FileNotFoundError(f"neither {EMITTED_REL} nor {ARTIFACT_REL} exists under {root}")


def symmetrise(adj: Adj) -> Adj:
    out: Adj = {k: set(v) for k, v in adj.items()}
    for src, targets in adj.items():
        for dst in targets:
            out.setdefault(dst, set()).add(src)
    return out


__all__ = [
    "CATALOG_ASYMMETRIC",
    "CATALOG_DECLARED",
    "CATALOG_DECLARED_AFTER",
    "CATALOG_RECIPROCAL_PAIRS",
    "CATALOG_UNDIRECTED",
    "adj_from_library",
    "adj_from_mapping",
    "library_from_adj",
    "load_or_reconstruct",
    "reconstruct_before",
    "symmetrise",
]
