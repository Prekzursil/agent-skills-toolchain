#!/usr/bin/env python3
"""Fixture inside-client probe against a plugin manifest.

Green only when the client can load hooks from a valid manifest. A corrupt
manifest must turn the probe red. A probe that stays green on a broken
manifest measures nothing (catalog both-states control).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_HOOK_KEYS = ("event", "command")
UNLOADED = "plugin-appears-installed-but-hooks-unloaded"


def load_manifest(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"unreadable:{type(exc).__name__}"
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        return None, "invalid-json"
    if not isinstance(doc, dict):
        return None, "not-an-object"
    return doc, "ok"


def hooks_loadable(doc: dict[str, Any]) -> tuple[bool, str]:
    name = doc.get("name")
    version = doc.get("version")
    hooks = doc.get("hooks")
    if not isinstance(name, str) or not name.strip():
        return False, "missing-name"
    if not isinstance(version, str) or not version.strip():
        return False, "missing-version"
    if not isinstance(hooks, list) or not hooks:
        return False, "hooks-unloaded"
    for i, hook in enumerate(hooks):
        if not isinstance(hook, dict):
            return False, f"hook[{i}]-not-object"
        for key in REQUIRED_HOOK_KEYS:
            val = hook.get(key)
            if not isinstance(val, str) or not val.strip():
                return False, f"hook[{i}]-missing-{key}"
    return True, "hooks-loaded"


def probe_plugin(manifest: Path) -> dict[str, Any]:
    """Return an inside-client observation record."""
    doc, why = load_manifest(manifest)
    if doc is None:
        return {
            "ok": False,
            "red": True,
            "observation_kinds": [],
            "reason": why,
            "hook_fired": False,
            "command_resolved": False,
            "client_version": "",
            "resolved_commands": [],
            "failure_class": UNLOADED,
            "hook_fired": False,
            "command_resolved": False,
            "failure_class": UNLOADED,
        }
    loaded, reason = hooks_loadable(doc)
    version = str(doc.get("version") or "") if loaded else ""
    commands = [h["command"] for h in doc["hooks"]] if loaded else []
    return {
        "ok": loaded,
        "red": not loaded,
        "observation_kinds": (
            ["hook_fired", "command_resolved"] if loaded else []
        ),
        "reason": reason,
        "hook_fired": loaded,
        "command_resolved": loaded,
        "client_version": version,
        "resolved_commands": commands,
        "failure_class": None if loaded else UNLOADED,
        "hook_fired": loaded,
        "command_resolved": loaded,
        "failure_class": None if loaded else UNLOADED,
    }


probe_plugin = probe_plugin
