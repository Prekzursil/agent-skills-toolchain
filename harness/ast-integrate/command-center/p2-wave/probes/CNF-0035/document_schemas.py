#!/usr/bin/env python3
"""additionalProperties:false schemas for the live generated manifests and configs."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

GENERATED = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "artifact_class",
        "generator_id",
        "generator_version",
        "registry_entry_sha256",
        "registry_id",
        "schema",
    ],
    "properties": {
        "artifact_class": {"type": "string", "minLength": 1},
        "generator_id": {"type": "string", "minLength": 1},
        "generator_version": {"type": "string", "minLength": 1},
        "registry_entry_sha256": {
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "registry_id": {"type": "string", "minLength": 1},
        "schema": {"type": "string", "minLength": 1},
    },
}

PLUGIN = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "A2 generated plugin.json",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "_generated",
        "description",
        "hooks",
        "name",
        "rules",
        "skills",
        "version",
    ],
    "properties": {
        "_generated": GENERATED,
        "description": {"type": "string", "minLength": 1},
        "hooks": {"type": "array", "items": {"type": "string"}},
        "name": {"type": "string", "minLength": 1},
        "rules": {"type": "array", "items": {"type": "string"}},
        "skills": {"type": "array", "items": {"type": "string"}},
        "version": {"type": "string", "minLength": 1},
    },
}

MARKETPLACE = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "A2 generated marketplace listing",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "_generated",
        "category",
        "description",
        "name",
        "plugin_id",
        "version",
    ],
    "properties": {
        "_generated": GENERATED,
        "category": {"type": "string", "minLength": 1},
        "description": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        "plugin_id": {"type": "string", "minLength": 1},
        "version": {"type": "string", "minLength": 1},
    },
}

HOOK = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "A2 generated hook config",
    "type": "object",
    "additionalProperties": False,
    "required": ["_generated", "enabled", "event", "id", "script"],
    "properties": {
        "_generated": GENERATED,
        "enabled": {"type": "boolean"},
        "event": {"type": "string", "minLength": 1},
        "id": {"type": "string", "minLength": 1},
        "script": {"type": "string", "minLength": 1},
    },
}

DISPATCH = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "hooks/_dispatch/manifest.json",
    "type": "object",
    "additionalProperties": False,
    "required": ["hooks", "mounts"],
    "properties": {
        "hooks": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "mounts": {"type": "array", "items": {"type": "string", "minLength": 1}},
    },
}

SETTINGS = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Frozen settings.json keys (catalog-named; no live credential file)",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "disabledMcpServers",
        "enabledPlugins",
        "hooks",
        "model",
        "permissions",
    ],
    "properties": {
        "disabledMcpServers": {
            "type": "array",
            "items": {"type": "string"},
        },
        "enabledPlugins": {"type": "object"},
        "hooks": {"type": "object"},
        "model": {"type": "string", "minLength": 1},
        "permissions": {"type": "object"},
    },
}

KIND_SCHEMA = {
    "plugin": PLUGIN,
    "marketplace": MARKETPLACE,
    "hook": HOOK,
    "dispatch": DISPATCH,
    "settings": SETTINGS,
}

LIVE_SUBJECTS = (
    {
        "kind": "plugin",
        "path": (
            "command-center/p2-wave/probes/ARC-0016/fixtures/"
            "hatch-run/typed/plugin.json"
        ),
        "role": "plugin-manifest",
    },
    {
        "kind": "marketplace",
        "path": (
            "command-center/p2-wave/probes/ARC-0016/fixtures/"
            "hatch-run/typed/marketplace/marketplace.harness.json"
        ),
        "role": "marketplace-manifest",
    },
    {
        "kind": "hook",
        "path": (
            "command-center/p2-wave/probes/ARC-0016/fixtures/"
            "hatch-run/typed/hooks/hook.pre-tool.json"
        ),
        "role": "hook-config",
    },
    {
        "kind": "dispatch",
        "path": (
            "command-center/p2-wave/probes/ARC-0007/fixtures/"
            "repo/hooks/_dispatch/manifest.json"
        ),
        "role": "hook-dispatch",
    },
    {
        "kind": "settings",
        "path": "command-center/p2-wave/probes/CNF-0035/fixtures/settings.control.json",
        "role": "settings-frozen-keys",
    },
)


def registry_schema() -> dict:
    path = REPO / "command-center/p2-wave/probes/ARC-0010/registry.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def schema_for(kind: str) -> dict:
    if kind == "registry":
        return registry_schema()
    if kind not in KIND_SCHEMA:
        raise KeyError(kind)
    return KIND_SCHEMA[kind]
