#!/usr/bin/env python3
"""Two-signal plugin enumerator for RES-0177.

Disk signal: a directory is a plugin only if it contains a parseable
``.claude-plugin/plugin.json`` with a non-empty ``name``. Bare directories
are noise, not plugins.

Listing signal: the client's own plugin list (JSON ``plugins[]`` and/or
the text capture of ``claude plugin list``).

A name is installed only when BOTH signals contain it. A lister that
treats every directory name as present is matching directory noise.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PLUGIN_JSON_REL = ".claude-plugin/plugin.json"
FABRICATED_NAME = "xyzzy-not-installed-res0177"
KNOWN_PRESENT = "hookify"
NOISE_DIR_NAME = "looks-like-plugin"

SKIP_DIR_NAMES = {
    ".claude-plugin",
    ".git",
    "commands",
    "hooks",
    "skills",
    "agents",
    "scripts",
    "cache",
    "installed",
    "marketplaces",
}


def load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def manifest_name(path: Path) -> str | None:
    doc = load_json(path)
    if not isinstance(doc, dict):
        return None
    name = doc.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


def disk_plugins(root: Path) -> dict[str, dict]:
    """Enumerate plugins from disk. Requires plugin.json; directory names do not count."""
    found: dict[str, dict] = {}
    if not root.is_dir():
        return found
    for pjson in sorted(root.rglob("plugin.json")):
        if pjson.parent.name != ".claude-plugin":
            continue
        name = manifest_name(pjson)
        if not name:
            continue
        plugin_root = pjson.parent.parent
        found[name] = {
            "name": name,
            "path": str(plugin_root),
            "manifest_path": str(pjson),
            "manifest": load_json(pjson),
        }
    return found


def listing_from_json(doc: Any) -> dict[str, dict]:
    found: dict[str, dict] = {}
    if doc is None:
        return found
    rows = doc
    if isinstance(doc, dict):
        rows = doc.get("plugins")
    if not isinstance(rows, list):
        return found
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        pid = row.get("id")
        if not isinstance(name, str) or not name.strip():
            if isinstance(pid, str) and "@" in pid:
                name = pid.split("@", 1)[0]
            elif isinstance(pid, str):
                name = pid
            else:
                continue
        name = name.strip()
        if not name:
            continue
        found[name] = {
            "name": name,
            "id": pid if isinstance(pid, str) else name,
            "enabled": row.get("enabled"),
            "row": row,
        }
    return found


def listing_from_text(text: str) -> dict[str, dict]:
    found: dict[str, dict] = {}
    if not text:
        return found
    # ``name@marketplace`` headings, or a bare name followed by Status:
    for match in re.finditer(r"^([A-Za-z0-9._-]+)(?:@([A-Za-z0-9._-]+))?\s*$", text, re.M):
        name = match.group(1)
        if name.lower() in {"installed", "plugins", "status"}:
            continue
        found[name] = {
            "name": name,
            "id": f"{name}@{match.group(2)}" if match.group(2) else name,
            "from": "text",
        }
    return found


def listing_plugins(json_path: Path | None, text_path: Path | None = None) -> dict[str, dict]:
    found: dict[str, dict] = {}
    if json_path is not None:
        found.update(listing_from_json(load_json(json_path)))
    if text_path is not None and text_path.is_file():
        for name, row in listing_from_text(text_path.read_text(encoding="utf-8")).items():
            found.setdefault(name, row)
    return found


def query(name: str, disk: dict, listing: dict) -> dict:
    on_disk = name in disk
    on_list = name in listing
    return {
        "name": name,
        "disk": on_disk,
        "listing": on_list,
        "present": on_disk and on_list,
        "disk_only": on_disk and not on_list,
        "listing_only": on_list and not on_disk,
    }


def join_inventory(disk: dict, listing: dict) -> list[dict]:
    names = sorted(set(disk) | set(listing))
    return [query(n, disk, listing) for n in names]


def installed_names(disk: dict, listing: dict) -> list[str]:
    return [row["name"] for row in join_inventory(disk, listing) if row["present"]]


def mutant_directory_noise(root: Path) -> dict[str, dict]:
    """Broken enumerator: every directory name is a plugin.

    This is the control the catalog names: a lister that reports everything
    as present is matching directory noise.
    """
    found: dict[str, dict] = {}
    if not root.is_dir():
        return found
    for path in root.rglob("*"):
        if not path.is_dir():
            continue
        if path.name in SKIP_DIR_NAMES or path.name.startswith("."):
            continue
        found[path.name] = {"name": path.name, "path": str(path), "noise_matched": True}
    return found
