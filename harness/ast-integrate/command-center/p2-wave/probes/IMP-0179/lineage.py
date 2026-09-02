#!/usr/bin/env python3
"""IMP-0179 lineage graph: fused/generated workflows carry non-droppable provenance.

Catalog target: record, for every generated or fused workflow, the exact source
components, their versions, their licences and the fusion strategy used.
Named failure class 'workflow provenance or license is lost' is a publish/export
refusal, not a warning. Round-trip is field-by-field equality, not 'key still present'.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

ENVELOPE_FORMAT = "imp-0179-lineage-envelope/v1"
FAILURE_CLASS = "workflow provenance or license is lost"
REFUSAL_ID = "FC-11334"
SPEC_ANCHOR = "_USER-PROMPTS.md:11334"

FUSED_STRATEGIES = frozenset(
    {
        "stage-splice",
        "common-core",
        "union",
        "best-of-breed",
        "conditional-hybrid",
        "ensemble",
        "progressive",
    }
)
GENERATED_STRATEGY = "direct-generation"
STRATEGIES = FUSED_STRATEGIES | {GENERATED_STRATEGY}
KINDS = frozenset({"fused", "generated"})
SOURCE_FIELDS = ("component_id", "version", "licence", "role")
LINEAGE_SCALAR_FIELDS = ("workflow_id", "kind", "fusion_strategy")


class LineageError(ValueError):
    def __init__(self, issues: list[dict[str, str]]):
        self.issues = issues
        super().__init__("; ".join(f"{i['path']}: {i['reason']}" for i in issues) or FAILURE_CLASS)


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(obj: Any) -> str:
    return hashlib.sha256(canonical_dumps(obj).encode("utf-8")).hexdigest()


def field_paths(obj: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Walk a JSON-shaped value into (path, scalar) pairs for field-by-field equality."""
    out: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for key in sorted(obj):
            path = f"{prefix}.{key}" if prefix else str(key)
            out.extend(field_paths(obj[key], path))
        return out
    if isinstance(obj, list):
        for idx, item in enumerate(obj):
            out.extend(field_paths(item, f"{prefix}[{idx}]"))
        return out
    out.append((prefix, obj))
    return out


def field_equality(left: Any, right: Any) -> list[dict[str, Any]]:
    """Return mismatches. Empty list means field-by-field equality."""
    a = dict(field_paths(left))
    b = dict(field_paths(right))
    mismatches: list[dict[str, Any]] = []
    for path in sorted(set(a) | set(b)):
        if path not in a:
            mismatches.append({"path": path, "left": None, "right": b[path], "kind": "missing-left"})
        elif path not in b:
            mismatches.append({"path": path, "left": a[path], "right": None, "kind": "missing-right"})
        elif a[path] != b[path]:
            mismatches.append({"path": path, "left": a[path], "right": b[path], "kind": "value"})
    return mismatches


def _issue(path: str, reason: str) -> dict[str, str]:
    return {"path": path, "reason": reason, "failure_class": FAILURE_CLASS}


def _normalise_source(raw: Any, index: int) -> tuple[dict[str, str] | None, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    prefix = f"lineage.sources[{index}]"
    if not isinstance(raw, dict):
        return None, [_issue(prefix, "source is not an object")]
    # licence is canonical; license is accepted only as an alias that is copied, never dropped.
    licence = raw.get("licence")
    if not _nonempty_str(licence) and _nonempty_str(raw.get("license")):
        licence = raw.get("license")
    source = {
        "component_id": raw.get("component_id"),
        "version": raw.get("version"),
        "licence": licence,
        "role": raw.get("role") or "source",
    }
    if _nonempty_str(raw.get("span")):
        source["span"] = str(raw["span"]).strip()
    for field in SOURCE_FIELDS:
        if not _nonempty_str(source.get(field)):
            issues.append(_issue(f"{prefix}.{field}", f"{field} missing or empty"))
    if issues:
        return None, issues
    return {k: str(v).strip() for k, v in source.items() if v is not None}, issues


def _normalise_edge(raw: Any, index: int) -> tuple[dict[str, str] | None, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    prefix = f"lineage.edges[{index}]"
    if not isinstance(raw, dict):
        return None, [_issue(prefix, "edge is not an object")]
    edge = {
        "from": raw.get("from"),
        "to": raw.get("to"),
        "kind": raw.get("kind") or "source-of",
    }
    for field in ("from", "to", "kind"):
        if not _nonempty_str(edge.get(field)):
            issues.append(_issue(f"{prefix}.{field}", f"{field} missing or empty"))
    if issues:
        return None, issues
    return {k: str(v).strip() for k, v in edge.items()}, issues


def validate_lineage_record(record: Any, workflow_id: str | None = None, kind: str | None = None) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if record is None:
        return [_issue("lineage", "missing (stripped or never attached)")]
    if not isinstance(record, dict):
        return [_issue("lineage", "not an object")]
    if not record:
        return [_issue("lineage", "empty object")]

    for field in LINEAGE_SCALAR_FIELDS:
        if not _nonempty_str(record.get(field)):
            issues.append(_issue(f"lineage.{field}", f"{field} missing or empty"))

    rec_kind = record.get("kind")
    strategy = record.get("fusion_strategy")
    if rec_kind not in KINDS and _nonempty_str(rec_kind):
        issues.append(_issue("lineage.kind", f"unknown kind {rec_kind!r}"))
    if _nonempty_str(strategy) and strategy not in STRATEGIES:
        issues.append(_issue("lineage.fusion_strategy", f"unknown strategy {strategy!r}"))
    if rec_kind == "fused" and strategy == GENERATED_STRATEGY:
        issues.append(_issue("lineage.fusion_strategy", "fused workflow cannot use direct-generation"))
    if rec_kind == "generated" and _nonempty_str(strategy) and strategy != GENERATED_STRATEGY:
        issues.append(_issue("lineage.fusion_strategy", "generated workflow must use direct-generation"))
    if workflow_id and record.get("workflow_id") != workflow_id:
        issues.append(_issue("lineage.workflow_id", "does not match workflow.workflow_id"))
    if kind and rec_kind and rec_kind != kind:
        issues.append(_issue("lineage.kind", "does not match workflow.kind"))

    sources = record.get("sources")
    if not isinstance(sources, list) or not sources:
        issues.append(_issue("lineage.sources", "must be a non-empty list"))
        sources = []
    seen_ids: list[str] = []
    for idx, item in enumerate(sources):
        normalised, src_issues = _normalise_source(item, idx)
        issues.extend(src_issues)
        if normalised:
            seen_ids.append(normalised["component_id"])

    edges = record.get("edges")
    if not isinstance(edges, list) or not edges:
        issues.append(_issue("lineage.edges", "must be a non-empty list"))
        edges = []
    for idx, item in enumerate(edges):
        normalised, edge_issues = _normalise_edge(item, idx)
        issues.extend(edge_issues)
        if normalised and workflow_id and normalised["to"] != workflow_id:
            issues.append(_issue(f"lineage.edges[{idx}].to", "edge must point at this workflow"))
        if normalised and seen_ids and normalised["from"] not in seen_ids:
            issues.append(
                _issue(
                    f"lineage.edges[{idx}].from",
                    "edge source is not in lineage.sources",
                )
            )
    return issues


def validate_workflow(workflow: Any) -> list[dict[str, str]]:
    if not isinstance(workflow, dict):
        return [_issue("workflow", "not an object")]
    issues: list[dict[str, str]] = []
    wid = workflow.get("workflow_id")
    kind = workflow.get("kind")
    if not _nonempty_str(wid):
        issues.append(_issue("workflow_id", "missing or empty"))
    if kind not in KINDS:
        issues.append(_issue("kind", "must be fused or generated"))
    stages = workflow.get("stages")
    if not isinstance(stages, list) or not stages:
        issues.append(_issue("stages", "must be a non-empty list"))
    issues.extend(validate_lineage_record(workflow.get("lineage"), wid if _nonempty_str(wid) else None, kind if kind in KINDS else None))
    return issues


def _edges_for(workflow_id: str, sources: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{"from": s["component_id"], "to": workflow_id, "kind": "source-of"} for s in sources]


def attach_lineage(
    workflow: dict[str, Any],
    *,
    sources: list[dict[str, Any]],
    fusion_strategy: str,
    kind: str | None = None,
) -> dict[str, Any]:
    """Only constructor for a publishable fused/generated workflow. Missing lineage cannot be attached as empty."""
    body = deepcopy(workflow)
    wid = body.get("workflow_id")
    if not _nonempty_str(wid):
        raise LineageError([_issue("workflow_id", "missing or empty")])
    rec_kind = kind or body.get("kind")
    if rec_kind not in KINDS:
        raise LineageError([_issue("kind", "must be fused or generated")])
    body["kind"] = rec_kind
    normalised_sources: list[dict[str, str]] = []
    issues: list[dict[str, str]] = []
    for idx, raw in enumerate(sources):
        item, src_issues = _normalise_source(raw, idx)
        issues.extend(src_issues)
        if item:
            normalised_sources.append(item)
    record = {
        "workflow_id": str(wid).strip(),
        "kind": rec_kind,
        "fusion_strategy": fusion_strategy,
        "sources": normalised_sources,
        "edges": _edges_for(str(wid).strip(), normalised_sources),
        "failure_class_if_lost": FAILURE_CLASS,
        "spec_anchor": SPEC_ANCHOR,
    }
    body["lineage"] = record
    issues.extend(validate_workflow(body))
    if issues:
        raise LineageError(issues)
    return body


def lineage_of(workflow: dict[str, Any]) -> dict[str, Any]:
    issues = validate_workflow(workflow)
    if issues:
        raise LineageError(issues)
    record = deepcopy(workflow["lineage"])
    # Canonicalise aliases so export/import cannot drop licence.
    sources = []
    for idx, raw in enumerate(record["sources"]):
        item, src_issues = _normalise_source(raw, idx)
        if src_issues or item is None:
            raise LineageError(src_issues)
        sources.append(item)
    edges = []
    for idx, raw in enumerate(record["edges"]):
        item, edge_issues = _normalise_edge(raw, idx)
        if edge_issues or item is None:
            raise LineageError(edge_issues)
        edges.append(item)
    return {
        "workflow_id": record["workflow_id"],
        "kind": record["kind"],
        "fusion_strategy": record["fusion_strategy"],
        "sources": sources,
        "edges": edges,
        "failure_class_if_lost": FAILURE_CLASS,
        "spec_anchor": SPEC_ANCHOR,
    }


_NODE_RANK = {
    "fused-workflow": 3,
    "generated-workflow": 3,
    "component": 1,
    "source": 1,
}


def _source_node(source: dict[str, str]) -> dict[str, Any]:
    cid = source["component_id"]
    node_type = "source" if cid.startswith("wf.") else "component"
    return {
        "id": cid,
        "type": node_type,
        "version": source["version"],
        "licence": source["licence"],
        "role": source["role"],
    }


def _merge_nodes(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Same id may appear as a workflow and later as a fusion source. Merge, don't drop licence."""
    merged = dict(left)
    for key, value in right.items():
        if key == "id":
            continue
        if key == "type":
            if _NODE_RANK.get(value, 0) > _NODE_RANK.get(merged.get("type"), 0):
                merged["type"] = value
            continue
        existing = merged.get(key)
        if existing in (None, ""):
            merged[key] = value
        elif value not in (None, "") and existing != value:
            raise LineageError(
                [_issue(f"graph.nodes[{left['id']}].{key}", f"conflicting values {existing!r} vs {value!r}")]
            )
    return merged


def graph_fragment(workflow: dict[str, Any]) -> dict[str, Any]:
    record = lineage_of(workflow)
    nodes = [
        {
            "id": record["workflow_id"],
            "type": "fused-workflow" if record["kind"] == "fused" else "generated-workflow",
            "fusion_strategy": record["fusion_strategy"],
            "kind": record["kind"],
        }
    ]
    for source in record["sources"]:
        nodes.append(_source_node(source))
    return {"nodes": nodes, "edges": deepcopy(record["edges"])}


def lineage_graph(workflows: list[dict[str, Any]]) -> dict[str, Any]:
    """Union of per-workflow fragments. Duplicate ids merge; licence/version conflicts refuse."""
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for workflow in workflows:
        frag = graph_fragment(workflow)
        for node in frag["nodes"]:
            existing = nodes.get(node["id"])
            nodes[node["id"]] = node if existing is None else _merge_nodes(existing, node)
        for edge in frag["edges"]:
            key = (edge["from"], edge["to"], edge["kind"])
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append(edge)
    return {
        "schema": "imp-0179-lineage-graph/v1",
        "failure_class_if_lost": FAILURE_CLASS,
        "nodes": [nodes[k] for k in sorted(nodes)],
        "edges": sorted(edges, key=lambda e: (e["from"], e["to"], e["kind"])),
    }


def export_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    """Portable envelope. Refuses rather than emitting a lineage-less document."""
    issues = validate_workflow(workflow)
    if issues:
        raise LineageError(issues)
    record = lineage_of(workflow)
    body = deepcopy(workflow)
    body["lineage"] = record
    return {
        "format": ENVELOPE_FORMAT,
        "failure_class_if_lost": FAILURE_CLASS,
        "workflow": body,
        "lineage": record,
        "graph": graph_fragment(body),
        "lineage_sha256": canonical_sha256(record),
    }


def import_workflow(envelope: Any) -> dict[str, Any]:
    """Restore a workflow. Missing lineage in the envelope is a hard refusal, not a default."""
    if not isinstance(envelope, dict):
        raise LineageError([_issue("envelope", "not an object")])
    if envelope.get("format") != ENVELOPE_FORMAT:
        raise LineageError([_issue("envelope.format", "unsupported or missing envelope format")])
    workflow = envelope.get("workflow")
    carried = envelope.get("lineage")
    if not isinstance(workflow, dict):
        raise LineageError([_issue("envelope.workflow", "missing")])
    if carried is None:
        raise LineageError([_issue("envelope.lineage", "missing (stripped envelope)")])
    restored = deepcopy(workflow)
    inner = restored.get("lineage")
    restored["lineage"] = deepcopy(carried)
    issues = validate_workflow(restored)
    if issues:
        raise LineageError(issues)
    canonical = lineage_of(restored)
    if inner is not None:
        restored_inner = deepcopy(workflow)
        inner_issues = validate_workflow(restored_inner)
        if inner_issues:
            raise LineageError(inner_issues)
        mismatches = field_equality(canonical, lineage_of(restored_inner))
        if mismatches:
            raise LineageError(
                [_issue("envelope.lineage", "envelope.lineage disagrees with workflow.lineage")]
            )
    restored["lineage"] = canonical
    return restored


def round_trip(workflow: dict[str, Any]) -> dict[str, Any]:
    original = lineage_of(workflow)
    restored = import_workflow(export_workflow(workflow))
    imported = lineage_of(restored)
    mismatches = field_equality(original, imported)
    sha_match = canonical_sha256(original) == canonical_sha256(imported)
    if mismatches and sha_match:
        raise LineageError([_issue("round_trip", "sha256 matched but field-by-field disagreed")])
    if (not mismatches) and (not sha_match):
        raise LineageError([_issue("round_trip", "field-by-field matched but sha256 disagreed")])
    return {
        "workflow_id": original["workflow_id"],
        "field_mismatches": mismatches,
        "field_equal": not mismatches,
        "sha256_before": canonical_sha256(original),
        "sha256_after": canonical_sha256(imported),
        "sha256_match": sha_match,
        "field_count": len(field_paths(original)),
        "pass": (not mismatches) and sha_match,
    }


def publish(workflow: Any) -> dict[str, Any]:
    """Publish path. Lineage-stripped or licence-stripped documents are REFUSED."""
    issues = validate_workflow(workflow) if isinstance(workflow, dict) else [_issue("workflow", "not an object")]
    if issues:
        return {
            "accepted": False,
            "refusal_id": REFUSAL_ID,
            "failure_class": FAILURE_CLASS,
            "spec_anchor": SPEC_ANCHOR,
            "issues": issues,
        }
    record = lineage_of(workflow)  # type: ignore[arg-type]
    return {
        "accepted": True,
        "refusal_id": None,
        "failure_class": None,
        "spec_anchor": SPEC_ANCHOR,
        "issues": [],
        "workflow_id": record["workflow_id"],
        "fusion_strategy": record["fusion_strategy"],
        "source_count": len(record["sources"]),
    }


def strip_lineage(workflow: dict[str, Any]) -> dict[str, Any]:
    """Planted mutant: same stages, no lineage. Must be refused at publish."""
    body = deepcopy(workflow)
    body.pop("lineage", None)
    return body


def strip_licences(workflow: dict[str, Any]) -> dict[str, Any]:
    """Planted mutant: lineage present but every licence removed."""
    body = deepcopy(workflow)
    lineage = deepcopy(body.get("lineage") or {})
    for source in lineage.get("sources") or []:
        if isinstance(source, dict):
            source.pop("licence", None)
            source.pop("license", None)
    body["lineage"] = lineage
    return body
