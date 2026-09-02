#!/usr/bin/env python3
"""Structural integrity gate on a typed causal hierarchy.

Fails (exit 2) when any of:
  (a) a claim-registry id has zero inbound attachment
  (b) a CAUSE node has neither children nor evidence
  (c) an edge endpoint id does not exist
  (d) the graph contains a cycle

Also attaches accepted residual risks and unknowns when those ledgers
are supplied. Missing live inputs are reported as input_error, not as
a silent zero.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

CAUSE_TYPES = {"CAUSE", "cause", "ROOT-CAUSE", "ROOT_CAUSE"}
MECH_TYPES = {"MECHANISM", "mechanism"}
RISK_ID_RE = re.compile(r"\b(RISK-[A-Z0-9][A-Z0-9._-]*)\b")
UNK_ID_RE = re.compile(r"\b(UNK-[A-Z0-9][A-Z0-9._-]*)\b")
CLAIM_ID_RE = re.compile(r"\b(CLM-[A-Z0-9][A-Z0-9._-]*)\b")


@dataclass
class Finding:
    code: str
    subject: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "subject": self.subject, "detail": self.detail}


@dataclass
class GateResult:
    findings: list[Finding] = field(default_factory=list)
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    input_error: str | None = None
    graph_nodes: int = 0
    graph_edges: int = 0

    @property
    def observed(self) -> str:
        if self.input_error:
            return "NOT-CHECKED"
        return "FIRED" if self.findings else "SILENT"

    @property
    def exit_code(self) -> int:
        if self.input_error:
            return 3
        return 2 if self.findings else 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "observed": self.observed,
            "exit_code": self.exit_code,
            "input_error": self.input_error,
            "findings_count": len(self.findings),
            "findings": [f.as_dict() for f in self.findings],
            "counts": self.counts,
            "graph_nodes": self.graph_nodes,
            "graph_edges": self.graph_edges,
        }


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def unwrap_graph(doc: Any) -> dict[str, Any]:
    if not isinstance(doc, dict):
        raise ValueError("graph is not an object")
    for key in ("graph", "hierarchy", "root_cause_hierarchy"):
        inner = doc.get(key)
        if isinstance(inner, dict) and (
            "nodes" in inner or "edges" in inner or "vertices" in inner
        ):
            return inner
    return doc


def node_id(node: Mapping[str, Any]) -> str:
    return str(node.get("id") or node.get("node_id") or "").strip()


def node_type(node: Mapping[str, Any]) -> str:
    return str(node.get("type") or node.get("kind") or node.get("node_type") or "").strip()


def edge_ends(edge: Mapping[str, Any]) -> tuple[str, str]:
    src = edge.get("from")
    if src is None:
        src = edge.get("source")
    if src is None:
        src = edge.get("parent")
    dst = edge.get("to")
    if dst is None:
        dst = edge.get("target")
    if dst is None:
        dst = edge.get("child")
    return str(src or "").strip(), str(dst or "").strip()


def evidence_of(node: Mapping[str, Any]) -> list[Any]:
    for key in ("evidence", "evidence_anchors", "anchors"):
        val = node.get(key)
        if val:
            return _as_list(val)
    return []


def attached_ids(node: Mapping[str, Any], *keys: str) -> list[str]:
    out: list[str] = []
    for key in keys:
        for item in _as_list(node.get(key)):
            if isinstance(item, Mapping):
                cid = str(item.get("id") or item.get("claim_id") or "").strip()
            else:
                cid = str(item).strip()
            if cid:
                out.append(cid)
    return out


def extract_ids_from_records(doc: Any, id_keys: Iterable[str]) -> list[str]:
    if doc is None:
        return []
    records: list[Any]
    if isinstance(doc, list):
        records = doc
    elif isinstance(doc, dict):
        records = None
        for key in (
            "claims",
            "records",
            "items",
            "entries",
            "risks",
            "unknowns",
        ):
            if isinstance(doc.get(key), list):
                records = doc[key]
                break
        if records is None:
            # dict keyed by id, skipping metadata keys
            skip = {"schema_version", "id", "unit_id", "title", "state"}
            records = [
                {"id": k, **(v if isinstance(v, dict) else {"value": v})}
                for k, v in doc.items()
                if k not in skip and not str(k).startswith("$")
            ]
    else:
        return []
    ids: list[str] = []
    for rec in records:
        if isinstance(rec, Mapping):
            cid = ""
            for key in id_keys:
                cid = str(rec.get(key) or "").strip()
                if cid:
                    break
            if cid:
                ids.append(cid)
        elif isinstance(rec, str) and rec.strip():
            ids.append(rec.strip())
    return ids


def parse_ledger_ids(text: str, pattern: re.Pattern[str]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(text):
        token = match.group(1)
        if token not in seen:
            seen.add(token)
            found.append(token)
    return found


def load_id_ledger(path: Path | None, json_keys: tuple[str, ...], text_re: re.Pattern[str]) -> tuple[list[str] | None, str | None]:
    """Return (ids, error). ids is None when the file is absent."""
    if path is None:
        return None, None
    if not path.is_file():
        return None, f"absent:{path.as_posix()}"
    if path.stat().st_size <= 0:
        return None, f"empty:{path.as_posix()}"
    if path.suffix.lower() == ".json":
        try:
            doc = load_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return None, f"unparseable:{path.as_posix()}:{type(exc).__name__}"
        ids = extract_ids_from_records(doc, json_keys)
        return ids, None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"unreadable:{path.as_posix()}:{type(exc).__name__}"
    return parse_ledger_ids(text, text_re), None


def collect_nodes_edges(graph: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = graph.get("nodes") or graph.get("vertices") or []
    edges = graph.get("edges") or graph.get("links") or []
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("nodes/edges must be arrays")
    out_nodes = [n for n in nodes if isinstance(n, dict)]
    out_edges = [e for e in edges if isinstance(e, dict)]
    # adjacency listed on nodes
    for node in out_nodes:
        nid = node_id(node)
        for child in _as_list(node.get("children") or node.get("child_ids")):
            cid = str(child).strip() if not isinstance(child, dict) else node_id(child)
            if nid and cid:
                out_edges.append({"from": nid, "to": cid, "kind": "child"})
    root_attachments = graph.get("attachments") or graph.get("claim_attachments") or []
    if isinstance(root_attachments, list):
        for row in root_attachments:
            if not isinstance(row, dict):
                continue
            src = str(row.get("node_id") or row.get("from") or "").strip()
            dst = str(
                row.get("claim_id")
                or row.get("risk_id")
                or row.get("to")
                or row.get("id")
                or ""
            ).strip()
            if src and dst:
                out_edges.append({"from": src, "to": dst, "kind": "attaches"})
    return out_nodes, out_edges


def cyclic_nodes(ids: Iterable[str], edges: list[tuple[str, str]]) -> set[str]:
    nodes = set(ids)
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for src, dst in edges:
        if src in adj and dst in nodes:
            adj[src].append(dst)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}
    stack: list[str] = []
    in_cycle: set[str] = set()

    def dfs(u: str) -> None:
        color[u] = GRAY
        stack.append(u)
        for v in adj[u]:
            if color[v] == WHITE:
                dfs(v)
            elif color[v] == GRAY:
                try:
                    i = stack.index(v)
                except ValueError:
                    i = 0
                in_cycle.update(stack[i:])
        stack.pop()
        color[u] = BLACK

    for n in nodes:
        if color[n] == WHITE:
            dfs(n)
    return in_cycle


def evaluate(
    graph_doc: Any,
    claim_ids: list[str] | None,
    risk_ids: list[str] | None = None,
    unknown_ids: list[str] | None = None,
) -> GateResult:
    result = GateResult()
    try:
        graph = unwrap_graph(graph_doc)
        nodes, edges = collect_nodes_edges(graph)
    except (TypeError, ValueError) as exc:
        result.input_error = f"graph-shape:{exc}"
        return result

    id_list = [node_id(n) for n in nodes]
    id_set = {i for i in id_list if i}
    result.graph_nodes = len(id_list)
    result.graph_edges = len(edges)

    if not id_set:
        result.findings.append(
            Finding("schema-invalid", "nodes", "graph has no node ids")
        )

    dup = sorted({i for i in id_list if i and id_list.count(i) > 1})
    for did in dup:
        result.findings.append(
            Finding("schema-invalid", did, "duplicate node id")
        )

    dangling = 0
    edge_pairs: list[tuple[str, str]] = []
    attach_targets: set[str] = set()
    children: dict[str, list[str]] = {i: [] for i in id_set}

    for edge in edges:
        src, dst = edge_ends(edge)
        kind = str(edge.get("kind") or edge.get("type") or "").strip().lower()
        if kind == "attaches":
            if src not in id_set:
                dangling += 1
                result.findings.append(
                    Finding(
                        "dangling-edge",
                        src or "<empty-from>",
                        f"attachment source does not exist; to={dst}",
                    )
                )
            if dst:
                attach_targets.add(dst)
            continue
        if not src or not dst:
            dangling += 1
            result.findings.append(
                Finding("dangling-edge", src or dst or "<empty>", "edge missing endpoint")
            )
            continue
        missing: list[str] = []
        if src not in id_set:
            missing.append(f"from={src}")
        if dst not in id_set:
            missing.append(f"to={dst}")
        if missing:
            dangling += 1
            result.findings.append(
                Finding(
                    "dangling-edge",
                    dst if dst not in id_set else src,
                    "endpoint id does not exist: " + ", ".join(missing),
                )
            )
            continue
        edge_pairs.append((src, dst))
        children.setdefault(src, []).append(dst)

    # mechanism field that looks like a node id must exist
    for edge in edges:
        mech = edge.get("mechanism_id")
        if mech is None:
            raw = str(edge.get("mechanism") or "").strip()
            if raw in id_set or re.match(r"^[A-Z]{2,12}-[A-Z0-9._-]+$", raw):
                mech = raw
        if mech:
            mid = str(mech).strip()
            if mid and mid not in id_set:
                dangling += 1
                result.findings.append(
                    Finding(
                        "dangling-edge",
                        mid,
                        "mechanism endpoint id does not exist",
                    )
                )

    cycle = cyclic_nodes(id_set, edge_pairs)
    if cycle:
        result.findings.append(
            Finding(
                "cycle-in-causal-graph",
                ",".join(sorted(cycle)),
                f"{len(cycle)} nodes participate in a cycle",
            )
        )

    empty_causes = 0
    cause_ids = [node_id(n) for n in nodes if node_type(n) in CAUSE_TYPES and node_id(n)]
    for node in nodes:
        if node_type(node) not in CAUSE_TYPES:
            continue
        nid = node_id(node)
        kids = children.get(nid) or []
        ev = evidence_of(node)
        if not kids and not ev:
            empty_causes += 1
            result.findings.append(
                Finding(
                    "empty-cause",
                    nid or "<no-id>",
                    "CAUSE node has neither children nor evidence",
                )
            )

    referenced: set[str] = set(attach_targets)
    for node in nodes:
        referenced.update(
            attached_ids(
                node,
                "attached_claim_ids",
                "attached_ids",
                "claim_ids",
                "claims",
                "attached_risk_ids",
                "risk_ids",
                "attached_unknown_ids",
                "unknown_ids",
            )
        )
    # inbound edge onto a claim/risk/unknown id that is also a node
    inbound: dict[str, int] = {i: 0 for i in id_set}
    for src, dst in edge_pairs:
        inbound[dst] = inbound.get(dst, 0) + 1
    for nid, deg in inbound.items():
        if deg > 0:
            referenced.add(nid)

    def orphans(ids: list[str] | None, code: str) -> tuple[int, int]:
        if ids is None:
            return 0, 0
        n_or = 0
        for cid in ids:
            if cid not in referenced:
                n_or += 1
                result.findings.append(
                    Finding(code, cid, "zero inbound attachment to any cause/graph node")
                )
        return n_or, len(ids)

    orphan_claims, total_claims = orphans(claim_ids, "orphaned-finding")
    orphan_risks, total_risks = orphans(risk_ids, "orphaned-risk")
    orphan_unk, total_unk = orphans(unknown_ids, "orphaned-unknown")

    result.counts = {
        "orphan_claims": {
            "numerator": orphan_claims,
            "denominator": total_claims if claim_ids is not None else 0,
        },
        "empty_causes": {"numerator": empty_causes, "denominator": len(cause_ids)},
        "dangling_edges": {"numerator": dangling, "denominator": max(len(edges), 1) if edges else 0},
        "cyclic_nodes": {"numerator": len(cycle), "denominator": max(len(id_set), 1) if id_set else 0},
        "orphan_risks": {
            "numerator": orphan_risks,
            "denominator": total_risks if risk_ids is not None else 0,
        },
        "orphan_unknowns": {
            "numerator": orphan_unk,
            "denominator": total_unk if unknown_ids is not None else 0,
        },
    }
    # dangling denominator: use actual edge count even when zero
    result.counts["dangling_edges"]["denominator"] = len(edges)
    result.counts["cyclic_nodes"]["denominator"] = len(id_list)
    return result


def load_graph(path: Path) -> tuple[Any | None, str | None]:
    if not path.is_file():
        return None, f"absent:{path.as_posix()}"
    if path.stat().st_size <= 0:
        return None, f"empty:{path.as_posix()}"
    try:
        return load_json(path), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"unparseable:{path.as_posix()}:{type(exc).__name__}"


def run_paths(
    graph_path: Path,
    claims_path: Path | None = None,
    risks_path: Path | None = None,
    unknowns_path: Path | None = None,
) -> GateResult:
    graph, gerr = load_graph(graph_path)
    if gerr or graph is None:
        r = GateResult()
        r.input_error = gerr or "graph-missing"
        return r
    claims, cerr = load_id_ledger(claims_path, ("id", "claim_id"), CLAIM_ID_RE)
    if claims_path is not None and cerr:
        r = GateResult()
        r.input_error = cerr
        return r
    risks, rerr = load_id_ledger(risks_path, ("id", "risk_id"), RISK_ID_RE)
    if risks_path is not None and rerr:
        r = GateResult()
        r.input_error = rerr
        return r
    unks, uerr = load_id_ledger(unknowns_path, ("id", "unknown_id"), UNK_ID_RE)
    if unknowns_path is not None and uerr:
        r = GateResult()
        r.input_error = uerr
        return r
    return evaluate(graph, claims, risks, unks)


def format_counts(counts: Mapping[str, Mapping[str, int]]) -> list[str]:
    order = (
        "orphan_claims",
        "empty_causes",
        "dangling_edges",
        "cyclic_nodes",
        "orphan_risks",
        "orphan_unknowns",
    )
    labels = {
        "orphan_claims": "orphan claims / total claims",
        "empty_causes": "empty cause nodes / total cause nodes",
        "dangling_edges": "dangling edges / total edges",
        "cyclic_nodes": "cyclic nodes / total nodes",
        "orphan_risks": "orphan risks / total risks",
        "orphan_unknowns": "orphan unknowns / total unknowns",
    }
    lines = []
    for key in order:
        row = counts.get(key) or {}
        num = int(row.get("numerator") or 0)
        den = int(row.get("denominator") or 0)
        lines.append(f"{key}={num}/{den} ({labels[key]})")
    return lines


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SYN-0002 structural integrity gate")
    p.add_argument("--graph", required=True)
    p.add_argument("--claims")
    p.add_argument("--risks")
    p.add_argument("--unknowns")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    result = run_paths(
        Path(args.graph),
        Path(args.claims) if args.claims else None,
        Path(args.risks) if args.risks else None,
        Path(args.unknowns) if args.unknowns else None,
    )
    payload = result.as_dict()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"observed={result.observed} exit_code={result.exit_code}")
        if result.input_error:
            print(f"input_error={result.input_error}")
        for line in format_counts(result.counts):
            print(line)
        for finding in result.findings:
            print(f"FINDING {finding.code} {finding.subject}: {finding.detail}")
        if not result.findings and not result.input_error:
            print("FINDINGS none")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
