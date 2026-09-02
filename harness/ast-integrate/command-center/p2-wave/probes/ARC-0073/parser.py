#!/usr/bin/env python3
"""Extract capability-to-authority rows from a design artifact.

Duplicate detection is a set operation on those rows. A prose field such as
singular=true is ignored. Explicit capability_to_authority tables are also
set-operated, but they are never the sole evidence: file_set + samples are
always parsed.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

META_ROLES = frozenset(
    {
        "index",
        "schema",
        "overlay",
        "primary",
        "supporting",
        "generated-artifact-marking",
        "negative-control-hand-edit",
    }
)
PROJECTION_ROLES = {
    "plugin-manifest": "plugin",
    "marketplace-entries": "marketplace",
    "skill-deployments": "skill",
    "hook-deployments": "hook",
    "rule-deployments": "rule",
    "docs": "doc",
    "workflow-catalog": "workflow_blueprint",
    "council-catalog": "council_preset",
}
STATIC_ROLES = {
    "skills": "skill",
    "hooks": "hook",
    "rules": "rule",
    "workflow-blueprints": "workflow_blueprint",
    "council-presets": "council_preset",
    "council-protocols": "council_protocol",
    "mcp-mounts": "mcp_mount",
}
KIND_ALIASES = {
    "skills": "skill",
    "skill": "skill",
    "hooks": "hook",
    "hook": "hook",
    "rules": "rule",
    "rule": "rule",
    "workflow-blueprints": "workflow_blueprint",
    "workflow_blueprint": "workflow_blueprint",
    "workflows": "workflow_blueprint",
    "council-presets": "council_preset",
    "council_preset": "council_preset",
    "council-protocols": "council_protocol",
    "council_protocol": "council_protocol",
    "mcp-mounts": "mcp_mount",
    "mcp_mount": "mcp_mount",
    "plugin": "plugin",
    "marketplace": "marketplace",
    "doc": "doc",
    "docs": "doc",
}


def canon_kind(raw: str | None) -> str | None:
    if not raw:
        return None
    return KIND_ALIASES.get(str(raw).strip().lower(), str(raw).strip().lower())


def _auth_key(row: dict) -> tuple[str, str]:
    return (str(row.get("authority") or ""), str(row.get("path") or ""))


def _uniq(rows: Iterable[dict]) -> list[dict]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[dict] = []
    for row in rows:
        key = (
            str(row.get("capability") or ""),
            str(row.get("capability_id") or ""),
            str(row.get("authority") or ""),
            str(row.get("path") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    out.sort(
        key=lambda r: (
            str(r.get("capability") or ""),
            str(r.get("capability_id") or ""),
            str(r.get("authority") or ""),
            str(r.get("path") or ""),
        )
    )
    return out


def _row(
    *,
    capability: str,
    capability_id: str,
    authority: str,
    path: str,
    via: str,
    architecture_id: str,
) -> dict:
    return {
        "capability": capability,
        "capability_id": capability_id,
        "authority": authority,
        "path": path,
        "via": via,
        "architecture_id": architecture_id,
    }


def derive_from_file_set(design: dict) -> list[dict]:
    """Parse file_set + samples into authority rows. Ignores prose flags."""
    arch = str(design.get("architecture_id") or design.get("id") or "UNKNOWN")
    file_set = [e for e in (design.get("file_set") or []) if isinstance(e, dict)]
    samples = [s for s in (design.get("samples") or []) if isinstance(s, dict)]

    static: dict[str, list[tuple[str, str]]] = defaultdict(list)
    projections: dict[str, list[tuple[str, str]]] = defaultdict(list)
    ssot_paths: list[str] = []

    for entry in file_set:
        role = str(entry.get("role") or "").strip()
        path = str(entry.get("path") or "").strip()
        if not role or not path or role in META_ROLES:
            continue
        if role == "ssot":
            ssot_paths.append(path)
            continue
        if role in PROJECTION_ROLES:
            projections[PROJECTION_ROLES[role]].append((path, role))
            continue
        if role in STATIC_ROLES:
            static[STATIC_ROLES[role]].append((path, role))

    sample_ids_by_kind: dict[str, list[str]] = defaultdict(list)
    for sample in samples:
        kind = canon_kind(sample.get("kind"))
        cap_id = str(sample.get("id") or "").strip()
        if kind:
            sample_ids_by_kind[kind].append(cap_id or f"{kind}:unidentified")

    kinds = set(static) | set(projections) | set(sample_ids_by_kind)
    rows: list[dict] = []

    for kind in sorted(kinds):
        cap_ids = sample_ids_by_kind.get(kind) or [f"{kind}:class"]
        static_hits = static.get(kind) or []
        proj_hits = projections.get(kind) or []
        authorities: list[tuple[str, str, str]] = []
        # (authority, path, via)

        for path, role in static_hits:
            authorities.append((f"{arch}:{role}", path, "file_set-static"))

        ssot_claims_kind = bool(ssot_paths) and (bool(proj_hits) or (kind in sample_ids_by_kind and not static_hits))
        if ssot_claims_kind:
            for sp in ssot_paths:
                authorities.append((f"{arch}:ssot", sp, "ssot"))
        elif proj_hits and not ssot_paths:
            for path, role in proj_hits:
                authorities.append((f"{arch}:{role}", path, "file_set-projection"))

        # Static + projection with an SSOT means two subsystems claim the class.
        if static_hits and proj_hits and ssot_paths:
            for sp in ssot_paths:
                authorities.append((f"{arch}:ssot", sp, "ssot-conflicts-static"))

        # Dedup authority tuples then emit one row per (cap_id, authority).
        seen_auth: set[tuple[str, str]] = set()
        unique_auth: list[tuple[str, str, str]] = []
        for auth, path, via in authorities:
            key = (auth, path)
            if key in seen_auth:
                continue
            seen_auth.add(key)
            unique_auth.append((auth, path, via))

        for cap_id in cap_ids:
            for auth, path, via in unique_auth:
                rows.append(
                    _row(
                        capability=kind,
                        capability_id=cap_id,
                        authority=auth,
                        path=path,
                        via=via,
                        architecture_id=arch,
                    )
                )
    return _uniq(rows)


def parse_explicit_table(design: dict) -> list[dict]:
    table = design.get("capability_to_authority")
    if not isinstance(table, list):
        return []
    arch = str(design.get("architecture_id") or design.get("id") or "UNKNOWN")
    rows: list[dict] = []
    for item in table:
        if not isinstance(item, dict):
            continue
        kind = canon_kind(item.get("capability") or item.get("kind"))
        cap_id = str(item.get("capability_id") or item.get("id") or "").strip()
        authority = str(item.get("authority") or "").strip()
        path = str(item.get("path") or "").strip()
        if not kind or not authority:
            continue
        rows.append(
            _row(
                capability=kind,
                capability_id=cap_id or f"{kind}:class",
                authority=authority,
                path=path,
                via="explicit-table",
                architecture_id=arch,
            )
        )
    return _uniq(rows)


def duplicates_by_capability(rows: list[dict], *, group: str = "capability") -> list[dict]:
    """Set operation: any group key with two or more distinct authorities fails."""
    buckets: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        key = str(row.get(group) or "")
        if not key:
            continue
        buckets[key].add(_auth_key(row))
    findings: list[dict] = []
    for key, auths in sorted(buckets.items()):
        if len(auths) >= 2:
            findings.append(
                {
                    "group": group,
                    "key": key,
                    "authority_count": len(auths),
                    "authorities": sorted(
                        [{"authority": a, "path": p} for a, p in auths],
                        key=lambda x: (x["authority"], x["path"]),
                    ),
                }
            )
    return findings


def evaluate(design: dict | None) -> dict[str, Any]:
    if not isinstance(design, dict):
        return {
            "ok": False,
            "error": "design-not-object",
            "rows": [],
            "rows_derived": [],
            "rows_explicit": [],
            "duplicates": [],
            "duplicates_by_id": [],
            "control_planes": [],
            "singular": False,
            "prose_ignored": True,
        }
    derived = derive_from_file_set(design)
    explicit = parse_explicit_table(design)
    rows = _uniq(derived + explicit)
    dups_class = duplicates_by_capability(rows, group="capability")
    dups_id = duplicates_by_capability(
        [r for r in rows if r.get("capability_id") and not str(r.get("capability_id")).endswith(":class")],
        group="capability_id",
    )
    dups = dups_class + [d for d in dups_id if d not in dups_class]
    planes = sorted({(r["authority"], r["path"]) for r in rows})
    return {
        "ok": True,
        "error": None,
        "architecture_id": str(design.get("architecture_id") or design.get("id") or "UNKNOWN"),
        "rows": rows,
        "rows_derived": derived,
        "rows_explicit": explicit,
        "duplicates": dups_class,
        "duplicates_by_id": dups_id,
        "control_planes": [{"authority": a, "path": p} for a, p in planes],
        "singular": len(dups_class) == 0 and len(dups_id) == 0 and len(rows) > 0,
        "zero_rows": len(rows) == 0,
        "prose_ignored": True,
        "prose_singular_field": design.get("singular"),
    }


def evaluate_path(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return evaluate(None) | {"ok": False, "error": f"missing:{path.as_posix()}"}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return evaluate(None) | {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
    result = evaluate(doc)
    result["source_path"] = path.as_posix()
    return result


def find_row(rows: list[dict], *, capability_id: str | None = None, capability: str | None = None, path_contains: str | None = None) -> list[dict]:
    hits = []
    for row in rows:
        if capability_id and str(row.get("capability_id") or "") != capability_id:
            continue
        if capability and str(row.get("capability") or "") != capability:
            continue
        if path_contains and path_contains not in str(row.get("path") or ""):
            continue
        hits.append(row)
    return hits
