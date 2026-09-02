#!/usr/bin/env python3
"""Crafted trees for REL-0001 bump-linter cases."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def plugin(version: str = "1.0.0", **overrides: Any) -> dict:
    doc = {
        "name": "harness",
        "version": version,
        "description": "REL-0001 baseline plugin package",
        "hooks": ["hooks/pre-tool.json"],
        "tool_permissions": ["Read", "Grep"],
        "skills": ["skills/skill.council/SKILL.md"],
    }
    doc.update(overrides)
    return doc


def marketplace(version: str = "1.0.0") -> dict:
    return {
        "name": "harness",
        "plugin_id": "plugin.harness",
        "version": version,
        "description": "Marketplace registry entry for the harness plugin",
        "category": "control-plane",
        "tool_permissions": ["Read", "Grep"],
    }


def pack() -> dict:
    return {
        "id": "pack.core",
        "version": "1.0.0",
        "blueprints": [
            {"id": "bp.alpha", "path": "blueprints/alpha.json"},
            {"id": "bp.beta", "path": "blueprints/beta.json"},
        ],
    }


def councilspec() -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "councilspec.schema.json",
        "title": "CouncilSpec",
        "type": "object",
        "required": ["id", "roles"],
        "properties": {
            "id": {"type": "string"},
            "roles": {"type": "array"},
            "voting": {"type": "object"},
        },
    }


def hook() -> dict:
    return {
        "id": "hook.pre-tool",
        "event": "PreToolUse",
        "script": "hooks/pre-tool.py",
        "stdin_schema": {
            "type": "object",
            "required": ["tool_name"],
        },
    }


def baseline(version: str = "1.0.0") -> dict[str, Any]:
    return {
        "plugin.json": plugin(version),
        "marketplace.json": marketplace(version),
        "pack.json": pack(),
        "schemas/councilspec.schema.json": councilspec(),
        "hooks/pre-tool.json": hook(),
        "docs/notes.txt": "baseline release notes\n",
        "blueprints/alpha.json": {"id": "bp.alpha", "title": "alpha"},
        "blueprints/beta.json": {"id": "bp.beta", "title": "beta"},
    }


def with_plugin(tree: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    out = copy.deepcopy(tree)
    doc = copy.deepcopy(out["plugin.json"])
    doc.update(overrides)
    out["plugin.json"] = doc
    if "version" in overrides and isinstance(out.get("marketplace.json"), dict):
        out["marketplace.json"]["version"] = overrides["version"]
    return out


def case_major_key_removed() -> dict[str, Any]:
    tree = with_plugin(baseline(), version="1.0.1")
    del tree["plugin.json"]["hooks"]
    return tree


def case_patch_only() -> dict[str, Any]:
    tree = with_plugin(baseline(), version="1.0.1")
    tree["docs/notes.txt"] = "patch-level note edit; no contract change\n"
    tree["plugin.json"]["description"] = "REL-0001 baseline plugin package (docs tweak)"
    return tree


def case_patch_only_no_bump() -> dict[str, Any]:
    """Same patch-only bytes, declared version left at 1.0.0 (under-bump)."""
    tree = baseline(version="1.0.0")
    tree["docs/notes.txt"] = "patch-level note edit; no contract change\n"
    tree["plugin.json"]["description"] = "REL-0001 baseline plugin package (docs tweak)"
    return tree


def case_permission_widen() -> dict[str, Any]:
    tree = with_plugin(baseline(), version="1.0.1")
    tree["plugin.json"]["tool_permissions"] = ["Read", "Grep", "Bash"]
    return tree


def case_rename_identical() -> dict[str, Any]:
    tree = baseline(version="1.0.0")
    notes = tree.pop("docs/notes.txt")
    tree["docs/renamed-notes.txt"] = notes
    return tree


def case_minor_optional() -> dict[str, Any]:
    tree = with_plugin(baseline(), version="1.0.1")
    tree["plugin.json"]["keywords"] = ["rel", "semver"]
    return tree


def case_minor_optional_declared_minor() -> dict[str, Any]:
    tree = with_plugin(baseline(), version="1.1.0")
    tree["plugin.json"]["keywords"] = ["rel", "semver"]
    return tree


def case_hook_signature() -> dict[str, Any]:
    tree = with_plugin(baseline(), version="1.0.1")
    tree["hooks/pre-tool.json"]["event"] = "PostToolUse"
    return tree


def case_blueprint_retire() -> dict[str, Any]:
    tree = with_plugin(baseline(), version="1.0.1")
    tree["pack.json"]["blueprints"] = [
        {"id": "bp.alpha", "path": "blueprints/alpha.json"}
    ]
    return tree


def case_schema_required() -> dict[str, Any]:
    tree = with_plugin(baseline(), version="1.0.1")
    tree["schemas/councilspec.schema.json"]["required"] = ["id", "roles", "voting"]
    return tree


CASES = {
    "baseline": baseline,
    "major-key-removed": case_major_key_removed,
    "patch-only": case_patch_only,
    "patch-only-no-bump": case_patch_only_no_bump,
    "major-permission-widen": case_permission_widen,
    "rename-identical": case_rename_identical,
    "minor-optional": case_minor_optional,
    "minor-optional-declared-minor": case_minor_optional_declared_minor,
    "major-hook-signature": case_hook_signature,
    "major-blueprint-retire": case_blueprint_retire,
    "major-schema-required": case_schema_required,
}


def write_tree(dest: Path, tree: dict[str, Any]) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    for rel, content in tree.items():
        path = dest / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, (dict, list)):
            path.write_text(dumps(content), encoding="utf-8")
        else:
            text = content if isinstance(content, str) else str(content)
            if not text.endswith("\n"):
                text += "\n"
            path.write_text(text, encoding="utf-8")
    return dest


def materialize(name: str, dest: Path | None = None) -> Path:
    if name not in CASES:
        raise KeyError(name)
    target = dest if dest is not None else HERE / "fixtures" / name
    if target.exists():
        for path in sorted(target.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
    return write_tree(target, CASES[name]())


def materialize_all(root: Path | None = None) -> dict[str, Path]:
    base = root if root is not None else HERE / "fixtures"
    return {name: materialize(name, base / name) for name in CASES}


if __name__ == "__main__":
    written = materialize_all()
    for name, path in written.items():
        print(f"{name} -> {path}")
