"""Phase-level graph sidecar: authored source, regeneration, and drift gate.

DEPENDENCY-GRAPH.json is the machine-derived *item* graph and sits behind V-GRAPH
byte-parity. Adding any top-level key there is the known red path. The phase
graph therefore lives in PHASE-GRAPH.json, regenerated from
`sources/phase-graph-authored.json`. Edges are authored from spec prose (each
carries a reason); they are not derived from WORK-UNIT-CATALOG.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # pragma: no cover - import shim for direct runs
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalog as cat

AUTHORED_NAME = "phase-graph-authored.json"
SIDECAR_NAME = "PHASE-GRAPH.json"
DERIVATION = "tools/command-center/phase_graph.py:build_sidecar"


def sidecar_path(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else cat.command_center_dir()
    return base / SIDECAR_NAME


def resolve_authored_path(root: Path | str | None = None) -> Path | None:
    base = Path(root) if root is not None else cat.command_center_dir()
    path = base / "sources" / AUTHORED_NAME
    return path if path.is_file() else None


def is_acyclic(edges: list[dict[str, Any]], nodes: list[str]) -> bool:
    succ: dict[str, list[str]] = defaultdict(list)
    indeg = {str(n): 0 for n in nodes}
    for edge in edges:
        src, dst = str(edge["from"]), str(edge["to"])
        indeg.setdefault(src, 0)
        indeg.setdefault(dst, 0)
        succ[src].append(dst)
        indeg[dst] += 1
    remaining = dict(indeg)
    queue = deque(n for n, d in remaining.items() if d == 0)
    seen = 0
    while queue:
        node = queue.popleft()
        seen += 1
        for dst in succ.get(node, []):
            remaining[dst] -= 1
            if remaining[dst] == 0:
                queue.append(dst)
    return seen == len(remaining)


def longest_path(edges: list[dict[str, Any]], nodes: list[str]) -> list[str]:
    """Kahn-layered longest path over every authored edge (HARD, SOFT, CONTESTED)."""
    succ: dict[str, list[str]] = defaultdict(list)
    indeg = {str(n): 0 for n in nodes}
    for edge in edges:
        src, dst = str(edge["from"]), str(edge["to"])
        succ[src].append(dst)
        indeg.setdefault(dst, 0)
        indeg.setdefault(src, 0)
        indeg[dst] += 1
    best = {n: [n] for n in indeg}
    remaining = dict(indeg)
    queue = deque(sorted(n for n, d in remaining.items() if d == 0))
    while queue:
        node = queue.popleft()
        for dst in succ.get(node, []):
            cand = best[node] + [dst]
            if len(cand) > len(best.get(dst, [dst])):
                best[dst] = cand
            remaining[dst] -= 1
            if remaining[dst] == 0:
                queue.append(dst)
    return max(best.values(), key=len)


def _is_path(nodes: list[str], edges: list[dict[str, Any]]) -> bool:
    pairs = {(str(e["from"]), str(e["to"])) for e in edges}
    return all((nodes[i], nodes[i + 1]) in pairs for i in range(len(nodes) - 1))


def computed_critical_path(
    edges: list[dict[str, Any]], nodes: list[str], declared: list[str]
) -> list[str]:
    measured = longest_path(edges, nodes)
    if (
        declared
        and len(declared) == len(measured)
        and _is_path([str(n) for n in declared], edges)
    ):
        return [str(n) for n in declared]
    return measured


def load_authored(root: Path) -> dict[str, Any]:
    src = resolve_authored_path(root)
    if src is None:
        raise FileNotFoundError(
            f"{root / 'sources' / AUTHORED_NAME} is missing — cannot regenerate "
            f"{SIDECAR_NAME}"
        )
    data = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{src} root is {type(data).__name__}, expected object")
    return data


def build_sidecar(root: Path) -> dict[str, Any]:
    authored = load_authored(root)
    phases = list(authored.get("phases") or [])
    edges = list(authored.get("edges") or [])
    ids = [str(p["id"]) for p in phases]
    declared = [str(n) for n in (authored.get("declared_critical_path") or [])]
    acyclic = is_acyclic(edges, ids)
    computed = computed_critical_path(edges, ids, declared)
    pre = list(authored.get("program_preconditions") or [])
    buckets = list(authored.get("allocation_buckets") or [])
    true_n = sum(1 for row in pre if str(row.get("verdict")) == "TRUE")
    not_checked = sum(1 for row in pre if str(row.get("verdict")) == "NOT-CHECKED")
    false_n = sum(1 for row in pre if str(row.get("verdict")) == "FALSE")
    return {
        "acyclic": acyclic,
        "allocation_bucket_sum": sum(int(b.get("planned_units") or 0) for b in buckets),
        "allocation_buckets": buckets,
        "artifact": SIDECAR_NAME,
        "author": authored.get("author"),
        "canonical_home": "command-center/PHASE-GRAPH.json",
        "computed_critical_path": computed,
        "critical_path_match": computed == declared and acyclic,
        "declared_critical_path": declared,
        "derivation": DERIVATION,
        "derived_from": f"sources/{AUTHORED_NAME}",
        "description": authored.get("description"),
        "edge_count": len(edges),
        "edges": edges,
        "not_derived_from_catalog": True,
        "phase_count": len(phases),
        "phases": phases,
        "program_preconditions": pre,
        "program_preconditions_false": false_n,
        "program_preconditions_not_checked": not_checked,
        "program_preconditions_true": true_n,
        "schema_version": authored.get("schema_version", 1),
        "status": "GATED",
        "unit": authored.get("unit", "CC-0016"),
    }


def dump_sidecar(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def write_sidecar(root: Path | str) -> Path:
    root = Path(root)
    path = sidecar_path(root)
    path.write_text(dump_sidecar(build_sidecar(root)), encoding="utf-8", newline="\n")
    return path


def sidecar_drift(root: Path | str) -> list[str]:
    """Empty iff the on-disk sidecar equals regeneration of the authored source.

    Also fails closed on a cyclic authored graph: regeneration matching a cycle
    is not a silent gate.
    """
    root = Path(root)
    if resolve_authored_path(root) is None:
        return [f"sources/{AUTHORED_NAME} missing"]
    path = sidecar_path(root)
    if not path.is_file():
        return [f"{SIDECAR_NAME} missing"]
    want = build_sidecar(root)
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"{SIDECAR_NAME} unreadable: {type(exc).__name__}"]
    findings: list[str] = []
    if got != want:
        findings.append(f"{SIDECAR_NAME} differs from regeneration of authored source")
    if not want.get("acyclic") or (
        isinstance(got, dict) and got.get("acyclic") is False
    ):
        findings.append(f"{SIDECAR_NAME} is not acyclic")
    return findings


def check(root: Path | str | None = None) -> int:
    base = Path(root) if root is not None else cat.command_center_dir()
    drift = sidecar_drift(base)
    if drift:
        for item in drift:
            print(item)
        print(f"FAILED:phase-graph drift={len(drift)}")
        return 1
    print("SUCCESS:phase-graph regeneration silent (acyclic, critical path matches)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(cat.command_center_dir()))
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail on sidecar drift instead of rewriting",
    )
    args = parser.parse_args(argv)
    root = Path(args.root)
    if args.check:
        return check(root)
    if resolve_authored_path(root) is None:
        print(f"FAILED:phase-graph sources/{AUTHORED_NAME} missing under {root}")
        return 1
    written = write_sidecar(root)
    print(f"SUCCESS:phase-graph wrote={written}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
