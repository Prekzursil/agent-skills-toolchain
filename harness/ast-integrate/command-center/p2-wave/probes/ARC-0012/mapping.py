"""A2 registry-entry kind -> generated output path.

The path function is the completeness contract: a registry row is complete
iff this relative path exists as a non-empty file. Hand-authored files
outside command-center/control-plane/A2/generated/ are not A2 outputs.
"""
from __future__ import annotations

from typing import Any, Mapping

GENERATED_ROOT = "command-center/control-plane/A2/generated"

# kind -> (subdir, extension)
KIND_LAYOUT: Mapping[str, tuple[str, str]] = {
    "plugin_manifest": ("plugin", ".json"),
    "marketplace_entry": ("marketplace", ".json"),
    "skill": ("skills", ".json"),
    "hook": ("hooks", ".json"),
    "rule": ("rules", ".json"),
    "doc": ("docs", ".md"),
    "workflow_blueprint": ("workflows", ".json"),
    "council_preset": ("council", ".json"),
    "workflow_catalog": ("catalogs", ".json"),
    "council_catalog": ("catalogs", ".json"),
}


def expected_rel(entry: Mapping[str, Any], generated_root: str = GENERATED_ROOT) -> str:
    kind = str(entry.get("kind") or "")
    eid = str(entry.get("id") or "").strip()
    if not eid:
        raise ValueError("registry entry missing id")
    if kind not in KIND_LAYOUT:
        raise ValueError(f"unknown registry kind {kind!r} for id {eid}")
    folder, ext = KIND_LAYOUT[kind]
    # ids are dotted tokens; keep them as filenames (no path separators)
    if "/" in eid or "\\" in eid or ".." in eid:
        raise ValueError(f"unsafe registry id {eid!r}")
    return f"{generated_root.rstrip('/')}/{folder}/{eid}{ext}"
