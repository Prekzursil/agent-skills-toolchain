"""Provenance closure: ADD (with anchor) or CORRECT (wrong citation).

Closure by fabrication is a failure, not a pass. A candidate without a
provenance anchor (path + sha256 + bytes) does not resolve an edge.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

# Named mutants live here so probes can call them without duplicating rules.

KNOWN_BAD_REINJECT = "wfa0002-known-bad-reinject"


def candidate_admissible(candidate: dict[str, Any] | None) -> bool:
    """A candidate resolves an edge only with a real provenance anchor."""
    if not isinstance(candidate, dict):
        return False
    prov = candidate.get("provenance")
    if not isinstance(prov, dict):
        return False
    path = str(prov.get("anchor_path") or "").strip()
    sha = str(prov.get("sha256") or "").strip()
    bytes_ = prov.get("bytes")
    if not path or path in {"/", ".", "fabricated"}:
        return False
    if len(sha) < 32:
        return False
    try:
        size = int(bytes_)
    except (TypeError, ValueError):
        return False
    if size <= 0:
        return False
    return True


def index_registry(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for cand in registry.get("candidates") or []:
        if not isinstance(cand, dict):
            continue
        name = str(cand.get("name") or "")
        cid = str(cand.get("id") or "")
        if name:
            out[name] = cand
        if cid:
            out[cid] = cand
    return out


def classify_ref(row: dict[str, Any]) -> dict[str, Any]:
    """ADD if A or B hits with an anchor; else CORRECT the citing blueprint."""
    a = row.get("A")
    b = row.get("B")
    name = row["name"]
    drift = row.get("drift")
    hit = a if a is not None else b
    if hit is None:
        return {
            "name": name,
            "disposition": "CORRECT",
            "reason": "no-skill-rule-plugin-workflow-of-that-name",
            "provenance": None,
            "drift": drift,
            "A_hit": False,
            "B_hit": False,
        }
    source = "filesystem" if a is not None else "git-HEAD"
    return {
        "name": name,
        "disposition": "ADD",
        "reason": "estate-hit-requires-registry-row-with-anchor",
        "provenance": {
            "anchor_path": str(hit.get("path") or ""),
            "bytes": int(hit.get("bytes") or 0),
            "sha256": str(hit.get("sha256") or ""),
            "source": source,
            "evidence_A": a is not None,
            "evidence_B": b is not None,
        },
        "drift": drift,
        "A_hit": a is not None,
        "B_hit": b is not None,
    }


def classify_all(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["name"]: classify_ref(row) for row in rows}


def naive_fabricate_candidates(names: list[str]) -> list[dict[str, Any]]:
    """Mutant: mint registry rows from the name alone. Must not resolve edges."""
    return [{"id": f"wf-{n}", "name": n} for n in names]


def filesystem_only_classify(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Mutant: trust A only. Misses repo-only HEAD hits; hides live-only drift."""
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = row["name"]
        a = row.get("A")
        if a is None:
            out[name] = {
                "name": name,
                "disposition": "CORRECT",
                "reason": "filesystem-only-miss",
                "provenance": None,
                "drift": None,
                "A_hit": False,
                "B_hit": bool(row.get("B")),
            }
        else:
            out[name] = {
                "name": name,
                "disposition": "ADD",
                "reason": "filesystem-only-hit",
                "provenance": {
                    "anchor_path": str(a.get("path") or ""),
                    "bytes": int(a.get("bytes") or 0),
                    "sha256": str(a.get("sha256") or ""),
                    "source": "filesystem",
                    "evidence_A": True,
                    "evidence_B": False,
                },
                "drift": None,
                "A_hit": True,
                "B_hit": bool(row.get("B")),
            }
    return out


def apply_fix(
    graph: dict[str, Any],
    registry: dict[str, Any],
    classifications: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    finding = graph.get("FINDING_unresolved_provenance") or {}
    edges = list(finding.get("unresolved_edges") or [])
    new_registry = deepcopy(registry)
    candidates = list(new_registry.get("candidates") or [])
    existing_names = {str(c.get("name") or "") for c in candidates}
    additions: list[dict[str, Any]] = []
    citation_errors: list[dict[str, Any]] = []
    rejected_fabrication: list[str] = []

    for name, cls in classifications.items():
        if cls["disposition"] == "ADD":
            prov = cls.get("provenance") or {}
            cand = {
                "id": f"wf-{name}",
                "name": name,
                "provenance": {
                    "anchor_path": prov.get("anchor_path"),
                    "bytes": prov.get("bytes"),
                    "sha256": prov.get("sha256"),
                    "source": prov.get("source"),
                },
                "drift": cls.get("drift"),
            }
            if not candidate_admissible(cand):
                rejected_fabrication.append(name)
                continue
            if name not in existing_names:
                candidates.append(cand)
                additions.append(cand)
                existing_names.add(name)
        elif cls["disposition"] == "CORRECT":
            for edge in edges:
                if edge.get("ref") == name:
                    citation_errors.append(
                        {
                            "blueprint": edge.get("blueprint"),
                            "ref": name,
                            "action": "mark-citation-error",
                            "reason": cls.get("reason"),
                        }
                    )

    new_registry["candidates"] = candidates
    closed_graph = deepcopy(graph)
    closed_finding = dict(closed_graph.get("FINDING_unresolved_provenance") or {})
    remaining = []
    resolved_edges = []
    citation_set = {row["ref"] for row in citation_errors}
    added_set = {c["name"] for c in additions}
    for edge in edges:
        ref = edge.get("ref")
        if ref in added_set:
            resolved_edges.append({**edge, "resolution": "ADD"})
        elif ref in citation_set:
            resolved_edges.append({**edge, "resolution": "CORRECT"})
        else:
            remaining.append(edge)
    closed_finding["unresolved_refs"] = sorted({e["ref"] for e in remaining})
    closed_finding["unresolved_edges"] = remaining
    closed_finding["resolved_edges"] = resolved_edges
    closed_finding["citation_errors"] = citation_errors
    closed_graph["FINDING_unresolved_provenance"] = closed_finding

    return {
        "registry": new_registry,
        "graph": closed_graph,
        "additions": additions,
        "citation_errors": citation_errors,
        "rejected_fabrication": rejected_fabrication,
        "added_names": sorted(added_set),
        "corrected_names": sorted(citation_set),
    }


def check_closure(graph: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    """Count unresolved provenance edges. Fabricated (no-anchor) rows do not close."""
    finding = graph.get("FINDING_unresolved_provenance") or {}
    edges = list(finding.get("unresolved_edges") or [])
    # Already-resolved edges from a prior apply_fix stay resolved.
    already = list(finding.get("resolved_edges") or [])
    citation_errors = {
        row.get("ref")
        for row in (finding.get("citation_errors") or [])
        if isinstance(row, dict)
    }
    by_name = index_registry(registry)
    unresolved: list[dict[str, Any]] = []
    resolved = 0
    for edge in already:
        if edge.get("resolution") in {"ADD", "CORRECT"}:
            resolved += 1
    for edge in edges:
        ref = str(edge.get("ref") or "")
        cand = by_name.get(ref)
        if candidate_admissible(cand):
            resolved += 1
            continue
        if ref in citation_errors:
            resolved += 1
            continue
        unresolved.append(edge)
    total = resolved + len(unresolved)
    rate = 1.0 if total == 0 else resolved / total
    return {
        "provenance_edges_total": total,
        "provenance_edges_resolved": resolved,
        "provenance_edges_unresolved": len(unresolved),
        "provenance_resolution_rate": rate,
        "unresolved_refs": sorted({e.get("ref") for e in unresolved}),
        "unresolved_edges": unresolved,
        "rate_is_one": rate == 1.0 and len(unresolved) == 0 and total > 0,
    }


def re_inject_known_bad(closed_graph: dict[str, Any], ref: str = KNOWN_BAD_REINJECT) -> dict[str, Any]:
    """Both-states bad graph: one known-bad ref re-enters unresolved_edges."""
    g = deepcopy(closed_graph)
    finding = dict(g.get("FINDING_unresolved_provenance") or {})
    edges = list(finding.get("unresolved_edges") or [])
    edges.append(
        {
            "blueprint": "BP-WFA0002-REINJECT",
            "ref": ref,
            "field": "prov",
        }
    )
    refs = list(finding.get("unresolved_refs") or [])
    if ref not in refs:
        refs.append(ref)
    finding["unresolved_edges"] = edges
    finding["unresolved_refs"] = refs
    g["FINDING_unresolved_provenance"] = finding
    return g
