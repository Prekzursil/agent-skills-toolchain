"""Load the original 466-node graph, or reconstruct a confirmation graph.

The Windows harness-restore copy of 08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json
is not in this worktree (catalog R-A22: it lived only on the restore host).
This module probes the documented locations, then — if absent — builds a
466-node / 1025-edge confirmation graph from live worktree files plus 40
fail-closed unresolved refs. It does not invent origins from node names.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

NODE_TARGET = 466
EDGE_TARGET = 1025
UNRESOLVED_REF_COUNT = 40
UNRESOLVED_EDGE_COUNT = 66
RESOLVED_TARGET = NODE_TARGET - UNRESOLVED_REF_COUNT  # 426

ORIGINAL_REL = "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json"
HARNESS = "C:/Users/Prekzursil/.claude/harness-restore-20260806"

ORIGINAL_PROBE_PATHS = (
    HARNESS + "/" + ORIGINAL_REL,
    str(Path.home() / ".claude/harness-restore-20260806" / ORIGINAL_REL),
    str(REPO / ORIGINAL_REL),
    str(REPO / "command-center" / ORIGINAL_REL),
    str(REPO / "command-center/wfa" / ORIGINAL_REL),
    str(REPO / "command-center/foundry" / ORIGINAL_REL),
)

SNAPSHOT = HERE / "fixtures" / "graph.json"

SKIP_PARTS = (
    "/WFA-0153/",
    "/__pycache__/",
    "/foundry/",
    "/.git/",
)

OK_SUFFIX = {".py", ".json", ".md", ".txt", ".yml", ".yaml"}


def original_probe_hits() -> list[dict[str, Any]]:
    rows = []
    for raw in ORIGINAL_PROBE_PATHS:
        p = Path(raw)
        rows.append(
            {
                "path": raw,
                "exists": p.is_file(),
                "bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    return rows


def original_present() -> Path | None:
    for row in original_probe_hits():
        if row["exists"]:
            return Path(row["path"])
    return None


def _ok_file(repo: Path, path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        rel = path.relative_to(repo).as_posix()
    except ValueError:
        return False
    if any(s in f"/{rel}/" or s in f"/{rel}" for s in SKIP_PARTS):
        return False
    if path.suffix.lower() not in OK_SUFFIX:
        return False
    try:
        if path.stat().st_size <= 0 or path.stat().st_size > 2_000_000:
            return False
    except OSError:
        return False
    return True


def candidate_files(repo: Path) -> list[str]:
    found: list[str] = []
    roots = [
        repo / "command-center/schema",
        repo / "command-center/lib",
        repo / "command-center/p2-wave",
        repo / "command-center/receipts",
        repo / "command-center",
    ]
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            paths = [root]
        else:
            paths = [p for p in root.rglob("*") if p.is_file()]
        for p in paths:
            if not _ok_file(repo, p):
                continue
            rel = p.relative_to(repo).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            found.append(rel)
    found.sort()
    return found


def unresolved_refs() -> list[dict[str, Any]]:
    """Forty distinct fail-closed citations.

    The original unresolved_refs token list lives inside the missing graph
    file. These ids are reconstruction placeholders, not claimed original
    tokens. cited_source is a missing harness-restore path; name is a live
    basename so a name-as-evidence resolver would wrongly pass.
    """
    documented = [
        f"{HARNESS}/{ORIGINAL_REL}",
        f"{HARNESS}/08-WORKFLOW-CANDIDATE-REGISTRY.json",
        f"{HARNESS}/08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md",
        f"{HARNESS}/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    ]
    rows: list[dict[str, Any]] = []
    # Name trap: live catalog basename, fabricated cited path.
    rows.append(
        {
            "id": "unref:name-trap-catalog",
            "name": "WORK-UNIT-CATALOG.json",
            "kind": "unresolved-ref",
            "cited_source": f"{HARNESS}/WORK-UNIT-CATALOG.json",
            "reconstruction": True,
            "name_trap": True,
        }
    )
    for i, src in enumerate(documented):
        rows.append(
            {
                "id": f"unref:documented-{i:02d}",
                "name": Path(src).name,
                "kind": "unresolved-ref",
                "cited_source": src,
                "reconstruction": True,
                "name_trap": False,
            }
        )
    while len(rows) < UNRESOLVED_REF_COUNT:
        i = len(rows)
        rows.append(
            {
                "id": f"unref:missing-skill-{i:02d}",
                "name": f"missing-skill-{i:02d}",
                "kind": "unresolved-ref",
                "cited_source": f"{HARNESS}/skills/missing-skill-{i:02d}/SKILL.md",
                "reconstruction": True,
                "name_trap": False,
            }
        )
    return rows[:UNRESOLVED_REF_COUNT]


def _edges(resolved_ids: list[str], unresolved_ids: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(src: str, dst: str, kind: str) -> bool:
        if src == dst:
            return False
        key = (src, dst)
        if key in seen:
            return False
        seen.add(key)
        out.append(
            {
                "id": f"e{len(out):04d}",
                "source": src,
                "target": dst,
                "kind": kind,
            }
        )
        return True

    for i in range(UNRESOLVED_EDGE_COUNT):
        add(
            resolved_ids[i % len(resolved_ids)],
            unresolved_ids[i % len(unresolved_ids)],
            "blueprint-to-unresolved-ref",
        )
    n = len(resolved_ids)
    skip = 1
    while len(out) < EDGE_TARGET and skip < n:
        for i in range(n):
            if len(out) >= EDGE_TARGET:
                break
            add(
                resolved_ids[i],
                resolved_ids[(i + skip) % n],
                "worktree-adjacent",
            )
        skip += 1
    if len(out) != EDGE_TARGET:
        raise RuntimeError(f"edge construction produced {len(out)} want {EDGE_TARGET}")
    return out


def build_graph(repo: Path) -> dict[str, Any]:
    files = candidate_files(repo)
    if len(files) < RESOLVED_TARGET:
        raise RuntimeError(
            f"not enough live files to reconstruct resolvable nodes: "
            f"{len(files)} < {RESOLVED_TARGET}"
        )
    chosen = files[:RESOLVED_TARGET]
    resolved_nodes = [
        {
            "id": f"wt:{i:04d}",
            "name": Path(rel).name,
            "kind": "worktree-file",
            "cited_source": rel,
            "reconstruction": True,
            "name_trap": False,
        }
        for i, rel in enumerate(chosen)
    ]
    urefs = unresolved_refs()
    nodes = resolved_nodes + urefs
    if len(nodes) != NODE_TARGET:
        raise RuntimeError(f"node construction produced {len(nodes)}")
    edges = _edges(
        [n["id"] for n in resolved_nodes],
        [n["id"] for n in urefs],
    )
    hits = original_probe_hits()
    return {
        "graph_id": "WFA-0153-confirmation-reconstruction",
        "source": "reconstructed-worktree",
        "original_graph_present": False,
        "original_probe_hits": hits,
        "declared_node_count": NODE_TARGET,
        "declared_edge_count": EDGE_TARGET,
        "declared_unresolved_ref_count": UNRESOLVED_REF_COUNT,
        "declared_unresolved_edge_count": UNRESOLVED_EDGE_COUNT,
        "published_v1_resolution_rate": 0.8109,
        "FINDING_unresolved_provenance": {
            "unresolved_refs": [n["id"] for n in urefs],
            "settling_probe": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/WFA-0153/probe1_settle.py"
            ),
            "note": (
                "Original unresolved_refs tokens are inside the missing "
                "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json. These 40 ids "
                "are reconstruction placeholders with fail-closed citations."
            ),
        },
        "nodes": nodes,
        "edges": edges,
    }


def try_load_original(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict):
        return None
    nodes = doc.get("nodes")
    edges = doc.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return None
    normalized = []
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            continue
        cited = n.get("cited_source") or n.get("source") or n.get("path") or n.get("origin")
        normalized.append(
            {
                "id": str(n.get("id") or n.get("name") or f"orig:{i:04d}"),
                "name": n.get("name") or n.get("id") or f"orig:{i:04d}",
                "kind": n.get("kind") or n.get("type") or "original",
                "cited_source": cited,
                "reconstruction": False,
                "name_trap": False,
            }
        )
    finding = doc.get("FINDING_unresolved_provenance") or {}
    return {
        "graph_id": "WFA-0153-original",
        "source": "original-harness-restore",
        "original_graph_present": True,
        "original_path": path.as_posix(),
        "original_probe_hits": original_probe_hits(),
        "declared_node_count": len(normalized),
        "declared_edge_count": len(edges),
        "declared_unresolved_ref_count": len(finding.get("unresolved_refs") or []),
        "declared_unresolved_edge_count": finding.get("unresolved_edge_count"),
        "published_v1_resolution_rate": doc.get("provenance_resolution_rate") or 0.8109,
        "FINDING_unresolved_provenance": finding
        or {
            "unresolved_refs": [],
            "settling_probe": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/WFA-0153/probe1_settle.py"
            ),
        },
        "nodes": normalized,
        "edges": edges,
    }


def write_snapshot(graph: dict[str, Any], path: Path = SNAPSHOT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")


def load_graph(repo: Path, *, rebuild: bool = False) -> dict[str, Any]:
    orig = original_present()
    if orig is not None:
        loaded = try_load_original(orig)
        if loaded is not None:
            write_snapshot(loaded)
            return loaded
    if not rebuild and SNAPSHOT.is_file():
        doc = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        nodes = doc.get("nodes") or []
        edges = doc.get("edges") or []
        if len(nodes) == NODE_TARGET and len(edges) == EDGE_TARGET:
            return doc
    graph = build_graph(repo)
    write_snapshot(graph)
    return graph
