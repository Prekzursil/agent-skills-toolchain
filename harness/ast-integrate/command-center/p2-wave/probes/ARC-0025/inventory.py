#!/usr/bin/env python3
"""Materialize the live A4 measurement corpus on this worktree.

Always-on inventory = A2 generated control-plane files (from the live
ARC-0010 registry + generator) plus the stdio MCP mount fixture.
Host trees (rules/, ~/.claude, BASELINE-SNAPSHOT, architecture libraries)
are absent here; that absence is recorded, not filled with estimates.

Catalogue N counts selectable capabilities (skill, workflow, council preset,
hook, rule, mcp mount). Plugin/marketplace/docs/catalogs are scaffolding.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GEN_DIR = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0010"
INVENTORY_ROOT = HERE / "fixtures" / "inventory"
MCP_SRC = HERE / "fixtures" / "mcp.stdio-echo.mount.json"

CATALOGUE_KINDS = frozenset(
    {
        "skill",
        "workflow_blueprint",
        "council_preset",
        "hook",
        "rule",
        "mcp_mount",
    }
)
SCAFFOLD_KINDS = frozenset(
    {
        "plugin_manifest",
        "marketplace_entry",
        "doc",
        "workflow_catalog",
        "council_catalog",
    }
)

KIND_BY_REL: dict[str, tuple[str, str]] = {}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _import_generator():
    sys.path.insert(0, str(GEN_DIR))
    import generator as G  # noqa: WPS433

    return G


def _kind_for_rel(rel: str, entry_kind: str, entry_id: str) -> None:
    KIND_BY_REL[rel] = (entry_kind, entry_id)


def materialize() -> dict[str, Any]:
    """Write inventory files (LF) and return the file table."""
    G = _import_generator()
    registry = G.load_default_registry()
    generated = G.generate(registry)
    KIND_BY_REL.clear()
    by_id = {e["id"]: e for e in registry["entries"]}
    for entry in registry["entries"]:
        _kind_for_rel(G.output_path(entry), entry["kind"], entry["id"])

    if INVENTORY_ROOT.exists():
        for p in INVENTORY_ROOT.rglob("*"):
            if p.is_file():
                p.unlink()
    INVENTORY_ROOT.mkdir(parents=True, exist_ok=True)

    files: list[dict[str, Any]] = []
    for rel in sorted(generated):
        raw = generated[rel].replace(b"\r\n", b"\n")
        dest = INVENTORY_ROOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        kind, eid = KIND_BY_REL[rel]
        role = "catalogue" if kind in CATALOGUE_KINDS else "scaffolding"
        files.append(
            {
                "id": eid,
                "kind": kind,
                "rel": rel,
                "path": dest.relative_to(REPO).as_posix(),
                "bytes": len(raw),
                "sha256": sha256_bytes(raw),
                "role": role,
                "source": "a2-ssot-generator",
            }
        )

    mcp_raw = MCP_SRC.read_bytes().replace(b"\r\n", b"\n")
    mcp_rel = "mcp/mcp.stdio-echo.mount.json"
    mcp_dest = INVENTORY_ROOT / mcp_rel
    mcp_dest.parent.mkdir(parents=True, exist_ok=True)
    mcp_dest.write_bytes(mcp_raw)
    files.append(
        {
            "id": "mcp.stdio-echo",
            "kind": "mcp_mount",
            "rel": mcp_rel,
            "path": mcp_dest.relative_to(REPO).as_posix(),
            "bytes": len(mcp_raw),
            "sha256": sha256_bytes(mcp_raw),
            "role": "catalogue",
            "source": "arc-0025-fixture",
        }
    )

    index_rows = []
    for row in files:
        if row["role"] != "catalogue":
            continue
        index_rows.append(
            {
                "id": row["id"],
                "kind": row["kind"],
                "path": row["rel"],
                "bytes": row["bytes"],
                "sha256": row["sha256"],
            }
        )
    index_rows.sort(key=lambda r: (r["kind"], r["id"]))
    index_lines = [
        json.dumps(r, sort_keys=True, separators=(",", ":")).encode("utf-8")
        for r in index_rows
    ]
    index_raw = b"\n".join(index_lines) + b"\n"
    index_dest = INVENTORY_ROOT / "INDEX.jsonl"
    index_dest.write_bytes(index_raw)
    files.append(
        {
            "id": "a4.index",
            "kind": "gateway_index",
            "rel": "INDEX.jsonl",
            "path": index_dest.relative_to(REPO).as_posix(),
            "bytes": len(index_raw),
            "sha256": sha256_bytes(index_raw),
            "role": "gateway_resident",
            "source": "arc-0025-index",
        }
    )

    gateway = {
        "architecture_id": "A4",
        "entry": "gateway",
        "selection": "task-selects-ids",
        "resident_when_nothing_selected": ["INDEX.jsonl", "GATEWAY.json"],
        "materializes": "selected catalogue ids only",
    }
    gw_raw = (
        json.dumps(gateway, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("utf-8")
    gw_dest = INVENTORY_ROOT / "GATEWAY.json"
    gw_dest.write_bytes(gw_raw)
    files.append(
        {
            "id": "a4.gateway",
            "kind": "gateway_stub",
            "rel": "GATEWAY.json",
            "path": gw_dest.relative_to(REPO).as_posix(),
            "bytes": len(gw_raw),
            "sha256": sha256_bytes(gw_raw),
            "role": "gateway_resident",
            "source": "arc-0025-stub",
        }
    )

    host = {
        "rules/": (REPO / "rules").is_dir(),
        "command-center/BASELINE-SNAPSHOT.json": (
            REPO / "command-center" / "BASELINE-SNAPSHOT.json"
        ).is_file(),
        "command-center/phase3/A4/DESIGN.json": (
            REPO / "command-center" / "phase3" / "A4" / "DESIGN.json"
        ).is_file(),
        "command-center/phase3/A1/COST.json": (
            REPO / "command-center" / "phase3" / "A1" / "COST.json"
        ).is_file(),
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json": (
            REPO / "09-WORKFLOW-BLUEPRINT-LIBRARY.json"
        ).is_file(),
    }

    activated_ids = {
        "skill.council",
        "wf.catalog-class.discovery-only",
        "mcp.stdio-echo",
    }
    return {
        "root": INVENTORY_ROOT.relative_to(REPO).as_posix(),
        "files": files,
        "index_rows": index_rows,
        "activated_ids": sorted(activated_ids),
        "host_present": host,
        "registry_path": (GEN_DIR / "registry.json").relative_to(REPO).as_posix(),
        "by_id": by_id,
    }
