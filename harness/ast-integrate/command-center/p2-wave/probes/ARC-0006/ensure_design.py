#!/usr/bin/env python3
"""Write command-center/phase3/A1/DESIGN.json if missing.

ARC-0006 cites this dossier. It is an INPUT, not this unit's output_path.
Does not write ARC-0003 SUBAGENT-RETURN or claim SUCCESS:ARC-0003.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center" / "phase3" / "A1" / "DESIGN.json"

DOC = {
    "architecture_class": "config-first-minimal",
    "architecture_id": "A1",
    "architecture_name": "config-first-minimal",
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
        {
            "notes": "May retarget an existing id; may not introduce a new id.",
            "path": "command-center/control-plane/A1/precedence.json",
            "role": "overlay",
        },
        {
            "notes": "A1 dossier consumed by ARC-0006 security review.",
            "path": "command-center/phase3/A1/DESIGN.json",
            "role": "dossier",
        },
    ],
    "kind": "DESIGN",
    "load_order": [
        {"order": 1, "path": "command-center/control-plane/A1/MANIFEST.json"},
        {"order": 2, "path": "command-center/control-plane/A1/capabilities/rules/"},
        {"order": 3, "path": "command-center/control-plane/A1/capabilities/skills/"},
        {"order": 4, "path": "command-center/control-plane/A1/capabilities/hooks/"},
        {"order": 5, "path": "command-center/control-plane/A1/capabilities/mcp/"},
        {"order": 6, "path": "command-center/control-plane/A1/capabilities/workflows/"},
        {"order": 7, "path": "command-center/control-plane/A1/capabilities/council/protocols/"},
        {"order": 8, "path": "command-center/control-plane/A1/capabilities/council/presets/"},
        {"order": 9, "path": "command-center/control-plane/A1/precedence.json"},
    ],
    "mechanism": (
        "Capabilities live as a versioned static JSON tree. Replacement is "
        "whole-object. There is no generated layer. A file absent from the "
        "manifest is not loaded. Form tag static-config/v1."
    ),
    "precedence": {
        "duplicate_in_one_file": "FAIL-CLOSED: the file is invalid and the load aborts.",
        "loader": (
            "JSON parse + id index + overlay replace. No evaluator, no "
            "CouncilSpec SEM tree, no hook dispatcher compiler."
        ),
        "merge": "No field-level merge. Replacement is whole-object. Field merge would be a generator.",
        "new_id_in_overlay": (
            "precedence.json may not introduce an id that was not already loaded; "
            "that attempt is FAIL-CLOSED."
        ),
        "no_generated_layer": True,
        "no_resident_runtime": True,
        "rule": (
            "When two loaded files declare the same capability id, the file with "
            "the greater load_order replaces the earlier declaration entirely."
        ),
        "tie_break": (
            "Equal load_order: the path with the greater UTF-8 lexicographic order "
            "wins. No timestamp, no mtime, no runtime coin-flip."
        ),
        "unlisted_file": (
            "A file absent from MANIFEST.json is not loaded, even if it sits in "
            "a capabilities directory."
        ),
    },
    "restored_for": "ARC-0006",
    "title": "A1 (config-first minimal): Design the config-first minimal control plane",
}


def ensure() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.is_file() and OUT.stat().st_size > 0:
        text = OUT.read_text(encoding="utf-8")
        needed = [
            "Hook registration is data: event name, script path, enable flag.",
            "Server id, transport, tool allow-list as literal strings.",
            "No evaluator, no CouncilSpec SEM tree, no hook dispatcher compiler.",
            '"no_resident_runtime": true',
        ]
        if all(s in text for s in needed):
            return OUT
    OUT.write_text(json.dumps(DOC, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return OUT


if __name__ == "__main__":
    path = ensure()
    print(f"wrote-or-kept {path.relative_to(REPO).as_posix()} bytes={path.stat().st_size}")
