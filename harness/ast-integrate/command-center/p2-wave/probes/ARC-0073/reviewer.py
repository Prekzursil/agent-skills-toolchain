#!/usr/bin/env python3
"""Independent authority-table re-derivation.

Walks file_set by reverse-sorted path and classifies authority from path
substrings rather than from the author parser's role maps. Two sampled
capabilities must match the parser's authority set.
"""
from __future__ import annotations

PATH_STATIC = (
    ("/capabilities/skills/", "skill"),
    ("/capabilities/hooks/", "hook"),
    ("/capabilities/rules/", "rule"),
    ("/capabilities/mcp/", "mcp_mount"),
    ("/capabilities/workflows/", "workflow_blueprint"),
    ("/capabilities/council/presets/", "council_preset"),
    ("/capabilities/council/protocols/", "council_protocol"),
)
PATH_PROJ = (
    ("/generated/skills", "skill"),
    ("/generated/hooks", "hook"),
    ("/generated/rules", "rule"),
    ("/generated/docs", "doc"),
    ("/generated/marketplace", "marketplace"),
    ("/generated/plugin", "plugin"),
    ("/generated/catalogs/workflows", "workflow_blueprint"),
    ("/generated/catalogs/council", "council_preset"),
)


def _norm(path: str) -> str:
    return path.replace("\\", "/")


def classify_path(path: str, role: str) -> tuple[str | None, str]:
    """Return (kind, plane) where plane is static|projection|ssot|meta."""
    p = _norm(path)
    role_l = (role or "").strip().lower()
    if role_l == "ssot" or p.endswith("REGISTRY.json") or p.endswith("/REGISTRY.json"):
        return None, "ssot"
    if role_l in {"index", "schema", "overlay"}:
        return None, "meta"
    for needle, kind in PATH_STATIC:
        if needle in p:
            return kind, "static"
    for needle, kind in PATH_PROJ:
        if needle in p:
            return kind, "projection"
    if role_l in {"skills", "hooks", "rules"}:
        return role_l.rstrip("s") if role_l != "rules" else "rule", "static"
    if role_l == "workflow-blueprints":
        return "workflow_blueprint", "static"
    if role_l == "council-presets":
        return "council_preset", "static"
    if role_l == "mcp-mounts":
        return "mcp_mount", "static"
    if role_l == "skill-deployments":
        return "skill", "projection"
    return None, "meta"


def hand_authorities(design: dict, capability_id: str) -> dict:
    samples = [s for s in (design.get("samples") or []) if isinstance(s, dict)]
    sample = next((s for s in samples if s.get("id") == capability_id), None)
    if sample is None:
        return {"capability_id": capability_id, "error": "sample-absent", "authorities": []}
    kind = str(sample.get("kind") or "")
    arch = str(design.get("architecture_id") or "UNKNOWN")
    entries = [e for e in (design.get("file_set") or []) if isinstance(e, dict)]
    entries = sorted(entries, key=lambda e: _norm(str(e.get("path") or "")), reverse=True)

    static_paths: list[str] = []
    proj_paths: list[str] = []
    ssot_paths: list[str] = []
    for entry in entries:
        path = str(entry.get("path") or "")
        role = str(entry.get("role") or "")
        k, plane = classify_path(path, role)
        if plane == "ssot":
            ssot_paths.append(path)
        elif plane == "static" and k == kind:
            static_paths.append(path)
        elif plane == "projection" and k == kind:
            proj_paths.append(path)

    auths: list[dict] = []
    for path in static_paths:
        auths.append({"authority": f"{arch}:static:{kind}", "path": path, "via": "path-static"})
    if ssot_paths and (proj_paths or (not static_paths)):
        for path in ssot_paths:
            auths.append({"authority": f"{arch}:ssot", "path": path, "via": "path-ssot"})
    if static_paths and proj_paths and ssot_paths:
        for path in ssot_paths:
            auths.append({"authority": f"{arch}:ssot", "path": path, "via": "path-ssot-conflict"})

    uniq = []
    seen = set()
    for row in auths:
        if row["path"] in seen:
            continue
        seen.add(row["path"])
        uniq.append(row)
    uniq.sort(key=lambda r: r["path"])
    return {
        "capability_id": capability_id,
        "kind": kind,
        "authorities": uniq,
        "authority_paths": [r["path"] for r in uniq],
        "error": None,
    }


def parser_paths_for_id(parser_rows: list[dict], capability_id: str) -> list[str]:
    paths = sorted(
        {
            str(r.get("path") or "")
            for r in parser_rows
            if r.get("capability_id") == capability_id and r.get("path")
        }
    )
    return paths


def match_parser(design: dict, parser_rows: list[dict], capability_id: str) -> dict:
    hand = hand_authorities(design, capability_id)
    parsed = parser_paths_for_id(parser_rows, capability_id)
    hand_paths = hand.get("authority_paths") or []
    return {
        "capability_id": capability_id,
        "kind": hand.get("kind"),
        "hand_paths": hand_paths,
        "parser_paths": parsed,
        "match": hand_paths == parsed and len(parsed) >= 1,
        "error": hand.get("error"),
    }
