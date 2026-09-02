#!/usr/bin/env python3
"""Generate mermaid architecture diagrams from live graphs.

Never writes command-center/DEPENDENCY-GRAPH.json (CI byte-parity gated).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

GATED = "command-center/DEPENDENCY-GRAPH.json"
PHASE_SIDECAR = "command-center/PHASE-GRAPH.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
DIAGRAM_DIR = "command-center/synthesis/diagrams"
GENERATOR_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0044/emit_set.py"
)
SENTINEL = (
    "SUCCESS:SYN-0044 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and counts match or the omission is "
    "captioned, and the parity gate is still green. Any other terminal state is "
    "FAILED:SYN-0044 <classification> with the diagnostic tail attached."
)
CRITICAL_PATH = ["0", "1", "2", "3", "4", "7", "7A", "10", "11", "14", "15"]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def gated_snapshot(repo: Path) -> dict[str, Any]:
    path = repo / GATED
    if not path.is_file():
        return {"present": False, "sha256": None, "bytes": 0}
    sha, size = digest_file(path)
    return {"present": True, "sha256": sha, "bytes": size}


def _phase_key(phase: str) -> tuple[int, str]:
    match = re.match(r"^(\d+)([A-Za-z]*)$", phase)
    if match:
        return (int(match.group(1)), match.group(2))
    return (10**6, phase)


def extract_nodes_edges(graph: dict[str, Any]) -> tuple[list[str], list[tuple[str, str]]]:
    nodes: list[str] = []
    seen: set[str] = set()
    raw_nodes = graph.get("nodes")
    if not raw_nodes:
        raw_nodes = graph.get("phases") or []
    for item in raw_nodes:
        if isinstance(item, dict):
            nid = str(item.get("id") or item.get("name") or "").strip()
        else:
            nid = str(item).strip()
        if nid and nid not in seen:
            seen.add(nid)
            nodes.append(nid)
    edges: list[tuple[str, str]] = []
    edge_seen: set[tuple[str, str]] = set()
    for item in graph.get("edges") or []:
        if not isinstance(item, dict):
            continue
        src = item.get("from") or item.get("src") or item.get("source")
        dst = (
            item.get("blocked_by")
            or item.get("to")
            or item.get("dst")
            or item.get("target")
        )
        if not src or not dst:
            continue
        pair = (str(src), str(dst))
        if pair not in edge_seen:
            edge_seen.add(pair)
            edges.append(pair)
    return nodes, edges


def _catalog_mod(repo: Path):
    sys.path.insert(0, str(repo / "tools" / "command-center"))
    import catalog as cat  # noqa: E402

    return cat


def load_catalog(repo: Path) -> dict[str, Any]:
    return _catalog_mod(repo).load(repo / CATALOG)


def derive_dependency_graph(repo: Path) -> dict[str, Any]:
    cat = _catalog_mod(repo)
    return cat.build_graph(cat.load(repo / CATALOG))


def load_dependency_source(repo: Path) -> dict[str, Any]:
    gated = repo / GATED
    catalog_path = repo / CATALOG
    if gated.is_file():
        data = json.loads(gated.read_text(encoding="utf-8"))
        nodes, edges = extract_nodes_edges(data)
        sha, size = digest_file(gated)
        return {
            "declared_path": GATED,
            "hashed_path": GATED,
            "present": True,
            "sha256": sha,
            "bytes": size,
            "loader": "disk",
            "nodes": nodes,
            "edges": edges,
        }
    data = derive_dependency_graph(repo)
    nodes, edges = extract_nodes_edges(data)
    sha, size = digest_file(catalog_path)
    return {
        "declared_path": GATED,
        "hashed_path": CATALOG,
        "present": False,
        "sha256": sha,
        "bytes": size,
        "loader": "catalog.build_graph in-memory; gated file not written",
        "nodes": nodes,
        "edges": edges,
    }


def derive_phase_graph(catalog: dict[str, Any]) -> dict[str, Any]:
    units = catalog.get("work_units") or []
    by_id = {
        str(u.get("id")): u for u in units if isinstance(u, dict) and u.get("id")
    }
    members: dict[str, list[str]] = {}
    for uid, unit in by_id.items():
        phase = str(unit.get("phase") or "UNKNOWN")
        members.setdefault(phase, []).append(uid)
    nodes = sorted(members, key=_phase_key)
    edges: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for unit in by_id.values():
        src_phase = str(unit.get("phase") or "UNKNOWN")
        for dep in unit.get("dependencies") or []:
            other = by_id.get(str(dep))
            if other is None:
                continue
            dep_phase = str(other.get("phase") or "UNKNOWN")
            if dep_phase == src_phase:
                continue
            pair = (dep_phase, src_phase)
            if pair not in seen:
                seen.add(pair)
                edges.append(pair)
    return {
        "nodes": [{"id": phase, "unit_count": len(members[phase])} for phase in nodes],
        "edges": [{"from": src, "to": dst} for src, dst in edges],
        "members": {phase: len(members[phase]) for phase in nodes},
    }


def _critical_path_from(data: dict[str, Any]) -> list[str]:
    cp = data.get("critical_path")
    if isinstance(cp, dict):
        path = [str(x).strip() for x in (cp.get("path") or []) if str(x).strip()]
        if path:
            return path
    if isinstance(cp, list):
        path = [str(x).strip() for x in cp if str(x).strip()]
        if path:
            return path
    return list(CRITICAL_PATH)


def load_phase_source(repo: Path) -> dict[str, Any]:
    sidecar = repo / PHASE_SIDECAR
    catalog_path = repo / CATALOG
    if sidecar.is_file():
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        nodes, edges = extract_nodes_edges(data)
        sha, size = digest_file(sidecar)
        return {
            "declared_path": PHASE_SIDECAR,
            "hashed_path": PHASE_SIDECAR,
            "present": True,
            "sha256": sha,
            "bytes": size,
            "loader": "disk",
            "nodes": nodes,
            "edges": edges,
            "critical_path": _critical_path_from(data if isinstance(data, dict) else {}),
        }
    data = derive_phase_graph(load_catalog(repo))
    nodes, edges = extract_nodes_edges(data)
    sha, size = digest_file(catalog_path)
    return {
        "declared_path": PHASE_SIDECAR,
        "hashed_path": CATALOG,
        "present": False,
        "sha256": sha,
        "bytes": size,
        "loader": "work_units[].phase in-memory; PHASE-GRAPH.json not written",
        "nodes": nodes,
        "edges": edges,
        "members": data.get("members") or {},
        "critical_path": list(CRITICAL_PATH),
    }


def load_architecture_source(repo: Path) -> dict[str, Any]:
    root = repo / "command-center" / "phase3"
    nodes: list[str] = []
    files: list[str] = []
    hashes: list[str] = []
    if root.is_dir():
        for path in sorted(root.glob("*/*.json")):
            rel = path.relative_to(repo).as_posix()
            files.append(rel)
            sha, _ = digest_file(path)
            hashes.append(f"{rel}:{sha}")
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            aid = str(doc.get("architecture_id") or "").strip()
            if aid and aid not in nodes:
                nodes.append(aid)
    inventory = "\n".join(hashes).encode("utf-8")
    return {
        "declared_path": "command-center/phase3/",
        "hashed_path": "command-center/phase3/",
        "present": root.is_dir(),
        "sha256": digest_bytes(inventory or b"absent"),
        "bytes": len(inventory),
        "loader": "phase3 architecture_id census",
        "nodes": nodes,
        "edges": [],
        "files": files,
        "chosen_record_present": False,
        "chosen_record_note": (
            "Bucket B06 chosen-architecture record is not on disk: PHASE-GRAPH.json "
            "is absent and no OWNER-DECISIONS.md names a Phase-3 winner. Nodes are "
            "architecture_id values actually present under command-center/phase3/."
        ),
    }


def mermaid_counts(text: str) -> tuple[int, int]:
    nodes = 0
    edges = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        if "-->" in stripped:
            edges += 1
        elif stripped.startswith("n") and '["' in stripped:
            nodes += 1
    return nodes, edges


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    rows: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if len(trial) <= width:
            current = trial
        else:
            rows.append(current)
            current = word
    rows.append(current)
    return rows


def render_mermaid(
    title: str,
    nodes: list[str],
    edges: list[tuple[str, str]],
    caption: str,
) -> str:
    lines = ["flowchart LR", f"  %% {title}", f"  %% {caption}"]
    for chunk in _wrap(caption, 88):
        lines.append(f"  %% {chunk}")
    index = {name: f"n{i}" for i, name in enumerate(nodes)}
    for name in nodes:
        label = name.replace('"', "'")
        lines.append(f'  {index[name]}["{label}"]')
    for src, dst in edges:
        if src in index and dst in index:
            lines.append(f"  {index[src]} --> {index[dst]}")
    lines.append("")
    return "\n".join(lines)


def write_diagram(repo: Path, name: str, mermaid: str) -> str:
    rel = f"{DIAGRAM_DIR}/{name}"
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    text = mermaid if mermaid.endswith("\n") else mermaid + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return rel


def diagram_record(
    *,
    did: str,
    source: dict[str, Any],
    source_nodes: list[str],
    source_edges: list[tuple[str, str]],
    rendered_nodes: list[str],
    rendered_edges: list[tuple[str, str]],
    mermaid: str,
    output_path: str,
    caption: str,
    omission_caption: str | None = None,
) -> dict[str, Any]:
    rendered_n, rendered_e = mermaid_counts(mermaid)
    rec: dict[str, Any] = {
        "id": did,
        "source_graph_path": source["hashed_path"],
        "declared_source_graph_path": source["declared_path"],
        "source_present": source["present"],
        "source_sha256": source["sha256"],
        "source_loader": source["loader"],
        "generator_command": GENERATOR_CMD,
        "output_path": output_path,
        "format": "mermaid",
        "source_node_count": len(source_nodes),
        "source_edge_count": len(source_edges),
        "rendered_node_count": rendered_n,
        "rendered_edge_count": rendered_e,
        "counts_match": rendered_n == len(source_nodes)
        and rendered_e == len(source_edges)
        and omission_caption is None,
        "caption": caption,
        "mermaid_sha256": digest_bytes(mermaid.encode("utf-8")),
        "mermaid_bytes": len(mermaid.encode("utf-8")),
        "rendered_node_ids": list(rendered_nodes),
        "rendered_edge_ids": [{"from": src, "to": dst} for src, dst in rendered_edges],
    }
    if omission_caption:
        rec["omission_caption"] = omission_caption
        rec["counts_match"] = False
    return rec


def mutate_graph(
    nodes: list[str], edges: list[tuple[str, str]]
) -> tuple[list[str], list[tuple[str, str]]]:
    planted = "SYN-0044-PLANTED"
    extra_nodes = list(nodes) + [planted]
    extra_edges = list(edges)
    if nodes:
        extra_edges.append((planted, nodes[0]))
    else:
        extra_edges.append((planted, planted))
    return extra_nodes, extra_edges


def build_diagrams(repo: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    dep = load_dependency_source(repo)
    phase = load_phase_source(repo)
    arch = load_architecture_source(repo)

    if dep["present"]:
        dep_caption = (
            f"Dependency-register diagram generated from on-disk {GATED} "
            f"(loader={dep['loader']}). Gated file present=True. "
            "SYN-0044 never writes that file. "
            f"Rendered {len(dep['nodes'])} nodes and {len(dep['edges'])} edges, matching the source."
        )
    else:
        dep_caption = (
            "Dependency-register diagram generated from catalog.build_graph. "
            f"Gated file {GATED} present=False. "
            "SYN-0044 never writes that file. "
            f"Rendered {len(dep['nodes'])} nodes and {len(dep['edges'])} edges, matching the derived source."
        )
    dep_mmd = render_mermaid("dependency-register", dep["nodes"], dep["edges"], dep_caption)
    dep_rel = write_diagram(repo, "SYN-0044-dependency.mmd", dep_mmd)
    dep_rec = diagram_record(
        did="dependency-register",
        source=dep,
        source_nodes=dep["nodes"],
        source_edges=dep["edges"],
        rendered_nodes=dep["nodes"],
        rendered_edges=dep["edges"],
        mermaid=dep_mmd,
        output_path=dep_rel,
        caption=dep_caption,
    )
    if not dep["present"]:
        dep_rec["source_absent_caption"] = (
            f"{GATED} is absent on disk. Counts are against the in-memory "
            "catalog.build_graph derivation. The gated file was not created."
        )

    if phase["present"]:
        phase_caption = (
            f"Phase diagram generated from on-disk {PHASE_SIDECAR} "
            f"(loader={phase['loader']}). Sidecar present=True. "
            f"Rendered {len(phase['nodes'])} nodes and {len(phase['edges'])} edges, matching the source."
        )
    else:
        phase_caption = (
            "Phase diagram derived from work_units[].phase. "
            f"{PHASE_SIDECAR} present=False. "
            f"Rendered {len(phase['nodes'])} nodes and {len(phase['edges'])} edges, matching the derived source. "
            "The authored sidecar was not on disk, so counts are against the in-memory derivation."
        )
    phase_mmd = render_mermaid("phase-full", phase["nodes"], phase["edges"], phase_caption)
    phase_rel = write_diagram(repo, "SYN-0044-phase-full.mmd", phase_mmd)
    phase_rec = diagram_record(
        did="phase-full",
        source=phase,
        source_nodes=phase["nodes"],
        source_edges=phase["edges"],
        rendered_nodes=phase["nodes"],
        rendered_edges=phase["edges"],
        mermaid=phase_mmd,
        output_path=phase_rel,
        caption=phase_caption,
    )

    cp_ids = phase.get("critical_path") or list(CRITICAL_PATH)
    present_cp = [name for name in cp_ids if name in set(phase["nodes"])]
    cp_edges = list(zip(present_cp, present_cp[1:]))
    omitted = [name for name in phase["nodes"] if name not in present_cp]
    omit_caption = (
        f"OMISSION: critical-path overlay renders {len(present_cp)} of "
        f"{len(phase['nodes'])} phase nodes and {len(cp_edges)} of "
        f"{len(phase['edges'])} derived edges. Omitted phases: "
        f"{', '.join(omitted) if omitted else '(none)'}. "
        "This overlay is not the full phase graph; see SYN-0044-phase-full.mmd."
    )
    cp_mmd = render_mermaid("phase-critical-path", present_cp, cp_edges, omit_caption)
    cp_rel = write_diagram(repo, "SYN-0044-phase-critical-path.mmd", cp_mmd)
    cp_rec = diagram_record(
        did="phase-critical-path",
        source=phase,
        source_nodes=phase["nodes"],
        source_edges=phase["edges"],
        rendered_nodes=present_cp,
        rendered_edges=cp_edges,
        mermaid=cp_mmd,
        output_path=cp_rel,
        caption=omit_caption,
        omission_caption=omit_caption,
    )

    arch_caption = arch["chosen_record_note"] + (
        f" Rendered {len(arch['nodes'])} architecture ids and 0 edges, matching the phase3 census."
    )
    arch_mmd = render_mermaid("architecture-b06-inventory", arch["nodes"], [], arch_caption)
    arch_rel = write_diagram(repo, "SYN-0044-architecture-b06.mmd", arch_mmd)
    arch_rec = diagram_record(
        did="architecture-b06-inventory",
        source=arch,
        source_nodes=arch["nodes"],
        source_edges=[],
        rendered_nodes=arch["nodes"],
        rendered_edges=[],
        mermaid=arch_mmd,
        output_path=arch_rel,
        caption=arch_caption,
    )
    arch_rec["phase3_files"] = arch.get("files") or []
    arch_rec["chosen_record_present"] = False

    sources = {"dependency": dep, "phase": phase, "architecture": arch}
    return [dep_rec, phase_rec, cp_rec, arch_rec], sources


def diagram_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain fields live under report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("diagrams"), list):
        return report
    return doc


def parity_gate_of(doc: dict[str, Any]) -> dict[str, Any]:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    gate = report.get("parity_gate") or doc.get("parity_gate") or {}
    return gate if isinstance(gate, dict) else {}
