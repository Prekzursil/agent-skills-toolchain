#!/usr/bin/env python3
"""Restore A1/A2/A6 DESIGN.json source dossiers this refute cites.

A9/DESIGN.json is not written (no ADV rebuild of ARC-0059). phase3/ on this
worktree currently holds only .gitkeep; the named-pair parser reads live
file_set rows from the A1/A2/A6 dossiers, so they must exist at the catalog
paths. Content is transcribed from the sibling emit_design.py file_set lists
(ARC-0003 / ARC-0010 / ARC-0038), not invented.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
A9_DESIGN = REPO / "command-center/phase3/A9/DESIGN.json"

A1 = {
    "architecture_class": "config-first-minimal",
    "architecture_id": "A1",
    "file_set": [
        {
            "notes": "Version, load_order listing, sha256 of every loaded file. Files not listed are not loaded.",
            "path": "command-center/control-plane/A1/MANIFEST.json",
            "role": "index",
        },
        {
            "notes": "One file per rule id. Static JSON only.",
            "path": "command-center/control-plane/A1/capabilities/rules/*.rule.json",
            "role": "rules",
        },
        {
            "notes": "One file per skill id.",
            "path": "command-center/control-plane/A1/capabilities/skills/*.skill.json",
            "role": "skills",
        },
        {
            "notes": "Hook registration is data: event name, script path, enable flag. No dispatcher generator.",
            "path": "command-center/control-plane/A1/capabilities/hooks/*.hook.json",
            "role": "hooks",
        },
        {
            "notes": "Server id, transport, tool allow-list as literal strings.",
            "path": "command-center/control-plane/A1/capabilities/mcp/*.mount.json",
            "role": "mcp-mounts",
        },
        {
            "notes": "Finite stage lists, declarative stopping (max_stages / halt). No eval.",
            "path": "command-center/control-plane/A1/capabilities/workflows/*.wf.json",
            "role": "workflow-blueprints",
        },
        {
            "notes": "Roles, voting, audit as JSON. Expression trees are forbidden.",
            "path": "command-center/control-plane/A1/capabilities/council/protocols/*.protocol.json",
            "role": "council-protocols",
        },
        {
            "notes": "Preset references a protocol id; may overlay declarative fields only.",
            "path": "command-center/control-plane/A1/capabilities/council/presets/*.preset.json",
            "role": "council-presets",
        },
    ],
    "kind": "DESIGN",
    "precedence": {
        "duplicate_in_one_file": "FAIL-CLOSED: the file is invalid and the load aborts.",
        "loader": "JSON parse + id index + overlay replace. No evaluator.",
        "no_generated_layer": True,
        "no_resident_runtime": True,
        "unlisted_file": "A file absent from MANIFEST.json is not loaded, even if it sits in a capabilities directory.",
    },
    "restored_as_source_dossier_for": "ARC-0065",
    "source_emit": "command-center/p2-wave/probes/ARC-0003/emit_design.py",
    "unit_id": "ARC-0003",
}

A2 = {
    "architecture_class": "generated-ssot",
    "architecture_id": "A2",
    "file_set": [
        {
            "notes": "Only hand-authored source of truth besides the schema. Typed entries, unique ids.",
            "path": "command-center/control-plane/A2/REGISTRY.json",
            "role": "ssot",
        },
        {
            "notes": "Draft-07 JSON Schema covering one entry of each generated artifact class.",
            "path": "command-center/control-plane/A2/registry.schema.json",
            "role": "schema",
        },
        {
            "notes": "Generated. Must not be hand-edited.",
            "path": "command-center/control-plane/A2/generated/plugin.json",
            "role": "plugin-manifest",
        },
        {
            "notes": "One generated JSON file per marketplace_entry.",
            "path": "command-center/control-plane/A2/generated/marketplace/",
            "role": "marketplace-entries",
        },
        {
            "notes": "Generated SKILL.md with provenance header.",
            "path": "command-center/control-plane/A2/generated/skills/",
            "role": "skill-deployments",
        },
        {
            "notes": "Generated hook JSON with _generated provenance.",
            "path": "command-center/control-plane/A2/generated/hooks/",
            "role": "hook-deployments",
        },
        {
            "notes": "Generated markdown rules.",
            "path": "command-center/control-plane/A2/generated/rules/",
            "role": "rule-deployments",
        },
        {
            "notes": "Generated documentation pages.",
            "path": "command-center/control-plane/A2/generated/docs/",
            "role": "docs",
        },
        {
            "notes": "Generated aggregate of workflow_blueprint members.",
            "path": "command-center/control-plane/A2/generated/catalogs/workflows.json",
            "role": "workflow-catalog",
        },
        {
            "notes": "Generated aggregate of council_preset members.",
            "path": "command-center/control-plane/A2/generated/catalogs/council.json",
            "role": "council-catalog",
        },
    ],
    "kind": "DESIGN",
    "restored_as_source_dossier_for": "ARC-0065",
    "source_emit": "command-center/p2-wave/probes/ARC-0010/emit_design.py",
    "unit_id": "ARC-0010",
}

A6 = {
    "architecture_class": "cross-vendor-adapter",
    "architecture_id": "A6",
    "file_set": [
        {
            "notes": "19 catalog fields plus A6 envelope. Loaded first.",
            "path": "command-center/control-plane/A6/CONTRACT.json",
            "role": "work-unit-and-artifact-contract",
        },
        {
            "notes": "Exactly-one-tier assignment per contract field, with citations.",
            "path": "command-center/control-plane/A6/TIERS.json",
            "role": "tier-map",
        },
        {
            "notes": "Capability bits plus mandatory leak register for Claude.",
            "path": "command-center/control-plane/A6/adapters/anthropic.json",
            "role": "vendor-adapter",
        },
        {
            "notes": "Capability bits plus mandatory leak register for Codex.",
            "path": "command-center/control-plane/A6/adapters/openai.json",
            "role": "vendor-adapter",
        },
        {
            "notes": "FAIL-CLOSED on GUARANTEED miss. Never silent downgrade.",
            "path": "command-center/control-plane/A6/NEGOTIATION.json",
            "role": "negotiation-algorithm",
        },
    ],
    "kind": "DESIGN",
    "restored_as_source_dossier_for": "ARC-0065",
    "source_emit": "command-center/p2-wave/probes/ARC-0038/emit_design.py",
    "unit_id": "ARC-0038",
}

TARGETS = (
    ("command-center/phase3/A1/DESIGN.json", A1),
    ("command-center/phase3/A2/DESIGN.json", A2),
    ("command-center/phase3/A6/DESIGN.json", A6),
)


def _unique_snippets(doc: dict, snippets: tuple[str, ...], rel: str) -> None:
    text = json.dumps(doc, indent=1, sort_keys=True)
    for snip in snippets:
        n = text.count(snip)
        if n != 1:
            raise SystemExit(f"FAILED:ARC-0065 dossier snippet hits={n} {rel!r} {snip!r}")


def write_dossiers() -> int:
    if A9_DESIGN.is_file():
        print("FAILED:ARC-0065 A9 DESIGN.json present; refusing ADV rebuild circle")
        return 1
    for rel, doc in TARGETS:
        path = REPO / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith("A1/DESIGN.json"):
            _unique_snippets(
                doc,
                (
                    "One file per skill id.",
                    "A file absent from MANIFEST.json is not loaded, even if it sits in a capabilities directory.",
                ),
                rel,
            )
        elif rel.endswith("A2/DESIGN.json"):
            _unique_snippets(
                doc,
                (
                    "Generated SKILL.md with provenance header.",
                    "Only hand-authored source of truth besides the schema. Typed entries, unique ids.",
                ),
                rel,
            )
        elif rel.endswith("A6/DESIGN.json"):
            _unique_snippets(
                doc,
                ("FAIL-CLOSED on GUARANTEED miss. Never silent downgrade.",),
                rel,
            )
        path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {rel} bytes={path.stat().st_size}")
    print("SUCCESS:ARC-0065 source dossiers restored (A9 DESIGN absent)")
    return 0


def main() -> int:
    return write_dossiers()


if __name__ == "__main__":
    raise SystemExit(main())
