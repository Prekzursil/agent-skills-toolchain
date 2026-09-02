"""Deterministic fixture-control corpus: 40 distinct refs, 66 unresolved edges.

Not the live 08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json (unread on this
worktree). Prefix wfa0002- so accidental live-tree collisions cannot mint
the catalog's original 40 ids.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
ESTATE = FIXTURES / "estate"
HEAD_BLOBS = FIXTURES / "head-blobs"
HEAD_INDEX_PATH = FIXTURES / "head-index.json"
GRAPH_PATH = FIXTURES / "graph.json"
REGISTRY_PATH = FIXTURES / "registry.json"

# 12 both-hit ADD (filesystem and independent HEAD)
ADD_BOTH: list[tuple[str, str]] = (
    [("wfa0002-skill-a-01", "skill-a"), ("wfa0002-skill-a-02", "skill-a"), ("wfa0002-skill-a-03", "skill-a")]
    + [("wfa0002-skill-b-01", "skill-b"), ("wfa0002-skill-b-02", "skill-b"), ("wfa0002-skill-b-03", "skill-b")]
    + [("wfa0002-rule-01", "rule"), ("wfa0002-rule-02", "rule")]
    + [("wfa0002-plugin-01", "plugin"), ("wfa0002-plugin-02", "plugin")]
    + [("wfa0002-workflow-01", "workflow"), ("wfa0002-workflow-02", "workflow")]
)

# 8 live-only: untracked filesystem hits that must NOT fool evidence B
LIVE_ONLY = [f"wfa0002-liveonly-{i:02d}" for i in range(1, 9)]

# 8 repo-only: HEAD hits with no live file
REPO_ONLY = [f"wfa0002-repoonly-{i:02d}" for i in range(1, 9)]

# 12 phantoms: citing blueprint is wrong; do not fabricate candidates
PHANTOM = [f"wfa0002-phantom-{i:02d}" for i in range(1, 13)]

KNOWN_BAD_REINJECT = "wfa0002-known-bad-reinject"

KIND_BY_REF: dict[str, str] = {}
for ref, kind in ADD_BOTH:
    KIND_BY_REF[ref] = kind
for i, ref in enumerate(LIVE_ONLY):
    KIND_BY_REF[ref] = ("skill-a", "skill-b", "rule", "plugin")[i % 4]
for ref in REPO_ONLY:
    KIND_BY_REF[ref] = "skill-a"
for ref in PHANTOM:
    KIND_BY_REF[ref] = "unknown"


def all_refs() -> list[str]:
    return [r for r, _ in ADD_BOTH] + LIVE_ONLY + REPO_ONLY + PHANTOM


def sha256_text(text: str) -> str:
    raw = text.encode("utf-8").replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def body_for(ref: str, kind: str) -> str:
    return (
        f"# {ref}\n\n"
        f"WFA-0002 fixture-control {kind}. Not a production skill/rule/plugin/workflow.\n"
        f"ref={ref}\n"
    )


def estate_relpath(ref: str, kind: str) -> str:
    if kind == "skill-a":
        return f"skills-a/{ref}/SKILL.md"
    if kind == "skill-b":
        return f"skills-b/{ref}/SKILL.md"
    if kind == "rule":
        return f"rules/{ref}.md"
    if kind == "plugin":
        return f"plugins/{ref}/plugin.json"
    if kind == "workflow":
        return f"workflows/{ref}.json"
    raise ValueError(kind)


def write_payload(path: Path, ref: str, kind: str) -> tuple[str, int]:
    text = body_for(ref, kind)
    if kind in {"plugin", "workflow"}:
        payload = {"id": ref, "kind": kind, "fixture": "WFA-0002", "body": text}
        raw = (json.dumps(payload, indent=1, sort_keys=True) + "\n").encode("utf-8")
    else:
        raw = text.encode("utf-8")
    raw = raw.replace(b"\r\n", b"\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest(), len(raw)


def unresolved_edges() -> list[dict[str, str]]:
    """66 edges over 40 distinct refs: first 26 refs cited twice."""
    refs = all_refs()
    if len(refs) != 40:
        raise RuntimeError(f"expected 40 refs, got {len(refs)}")
    edges: list[dict[str, str]] = []
    for i, ref in enumerate(refs, 1):
        bp = f"BP-WFA0002-{i:03d}"
        edges.append({"blueprint": bp, "ref": ref, "field": "prov"})
    for i, ref in enumerate(refs[:26], 1):
        bp = f"BP-WFA0002-X{i:02d}"
        edges.append({"blueprint": bp, "ref": ref, "field": "prov"})
    if len(edges) != 66:
        raise RuntimeError(f"expected 66 edges, got {len(edges)}")
    return edges


def build_graph() -> dict[str, Any]:
    refs = all_refs()
    edges = unresolved_edges()
    return {
        "artifact": "WFA-0002-fixture-control-provenance-graph",
        "discovery_only": True,
        "not_the_live_466_node_graph": True,
        "catalog_claimed": {
            "nodes": 466,
            "edges": 1025,
            "unresolved_edges": 66,
            "distinct_unresolved_refs": 40,
            "provenance_resolution_rate": 0.8109,
            "unread": True,
        },
        "FINDING_unresolved_provenance": {
            "unresolved_refs": refs,
            "unresolved_edges": edges,
            "settling_probe": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/WFA-0002/probe1_closure_rate.py"
            ),
        },
        "honesty": {
            "invented_original_40": False,
            "note": (
                "These 40 ids are fixture-control refs with prefix wfa0002-. "
                "They are not claimed to be the unread catalog graph's 40 names."
            ),
        },
    }


def build_registry() -> dict[str, Any]:
    # Two already-closed candidates so ADD cannot be "the registry was empty".
    return {
        "artifact": "WFA-0002-fixture-control-registry-slice",
        "not_the_284_row_registry": True,
        "candidates": [
            {
                "id": "wf-wfa0002-already-closed",
                "name": "wfa0002-already-closed",
                "provenance": {
                    "anchor_path": "fixtures/estate/workflows/wfa0002-already-closed.json",
                    "bytes": 2,
                    "sha256": sha256_text("{}\n"),
                    "source": "filesystem",
                },
            }
        ],
    }


def materialize() -> dict[str, Any]:
    """Write estate files + independent HEAD index. Idempotent."""
    if ESTATE.exists():
        # Drop previous generated files but keep the directory tree rebuildable.
        for p in ESTATE.rglob("*"):
            if p.is_file():
                p.unlink()
    if HEAD_BLOBS.exists():
        for p in HEAD_BLOBS.rglob("*"):
            if p.is_file():
                p.unlink()

    head_entries: dict[str, Any] = {}
    written_estate: list[str] = []

    for ref, kind in ADD_BOTH:
        rel = estate_relpath(ref, kind)
        path = ESTATE / rel
        digest, size = write_payload(path, ref, kind)
        written_estate.append(rel)
        head_entries[ref] = {
            "path": rel,
            "bytes": size,
            "sha256": digest,
            "kind": kind,
            "in_head": True,
        }

    live_only_written: list[str] = []
    for ref in LIVE_ONLY:
        kind = KIND_BY_REF[ref]
        rel = estate_relpath(ref, kind)
        path = ESTATE / rel
        write_payload(path, ref, kind)
        live_only_written.append(rel)
        # Deliberately omitted from head_entries.

    for ref in REPO_ONLY:
        kind = KIND_BY_REF[ref]
        blob = HEAD_BLOBS / f"{ref}.body"
        digest, size = write_payload(blob, ref, kind)
        head_entries[ref] = {
            "path": f"head-blobs/{ref}.body",
            "bytes": size,
            "sha256": digest,
            "kind": kind,
            "in_head": True,
            "repo_only": True,
        }

    # Closed control file so the pre-existing registry candidate is not a lie.
    closed_rel = "workflows/wfa0002-already-closed.json"
    closed_path = ESTATE / closed_rel
    closed_path.parent.mkdir(parents=True, exist_ok=True)
    closed_raw = b"{}\n"
    closed_path.write_bytes(closed_raw)

    graph = build_graph()
    registry = build_registry()
    registry["candidates"][0]["provenance"]["bytes"] = len(closed_raw)
    registry["candidates"][0]["provenance"]["sha256"] = hashlib.sha256(
        closed_raw
    ).hexdigest()

    head_index = {
        "method": "fixture-head-index",
        "independent_of_live_untracked": True,
        "note": (
            "Evidence B. Lookup is this index (or git ls-tree when a real HEAD "
            "exists). An untracked file under estate/ cannot appear here."
        ),
        "entries": head_entries,
    }

    FIXTURES.mkdir(parents=True, exist_ok=True)
    HEAD_INDEX_PATH.write_text(
        json.dumps(head_index, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    GRAPH_PATH.write_text(
        json.dumps(graph, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    REGISTRY_PATH.write_text(
        json.dumps(registry, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    refs = all_refs()
    return {
        "refs": refs,
        "n_refs": len(refs),
        "n_edges": len(unresolved_edges()),
        "add_both": [r for r, _ in ADD_BOTH],
        "live_only": list(LIVE_ONLY),
        "repo_only": list(REPO_ONLY),
        "phantom": list(PHANTOM),
        "known_bad_reinject": KNOWN_BAD_REINJECT,
        "graph": graph,
        "registry": registry,
        "head_index": head_index,
        "estate_root": str(ESTATE),
        "written_estate": written_estate,
        "live_only_written": live_only_written,
        "paths": {
            "head_index": str(HEAD_INDEX_PATH),
            "graph": str(GRAPH_PATH),
            "registry": str(REGISTRY_PATH),
        },
    }


def load_materialized() -> dict[str, Any]:
    if not GRAPH_PATH.is_file() or not HEAD_INDEX_PATH.is_file():
        return materialize()
    return {
        "refs": all_refs(),
        "n_refs": 40,
        "n_edges": 66,
        "add_both": [r for r, _ in ADD_BOTH],
        "live_only": list(LIVE_ONLY),
        "repo_only": list(REPO_ONLY),
        "phantom": list(PHANTOM),
        "known_bad_reinject": KNOWN_BAD_REINJECT,
        "graph": json.loads(GRAPH_PATH.read_text(encoding="utf-8")),
        "registry": json.loads(REGISTRY_PATH.read_text(encoding="utf-8")),
        "head_index": json.loads(HEAD_INDEX_PATH.read_text(encoding="utf-8")),
        "estate_root": str(ESTATE),
        "paths": {
            "head_index": str(HEAD_INDEX_PATH),
            "graph": str(GRAPH_PATH),
            "registry": str(REGISTRY_PATH),
        },
    }
