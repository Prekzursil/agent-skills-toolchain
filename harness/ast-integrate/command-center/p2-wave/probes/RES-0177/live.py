#!/usr/bin/env python3
"""Live-install scan. Honest absence is a measurement, not a detector failure."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from enumerate import disk_plugins, listing_plugins

LIVE_PLUGIN_ROOTS = (
    Path.home() / ".claude" / "plugins",
)

LIVE_LISTING_CANDIDATES = (
    Path.home() / ".claude" / "plugins" / "installed_plugins.json",
    Path.home() / ".claude" / "plugins" / "installed_plugins.json",
)

LIVE_SKILLS = (
    Path.home() / ".claude" / "skills",
    Path.home() / ".agents" / "skills",
    Path.home() / ".claude" / "skills",
)


def _exists(path: Path) -> dict:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "is_file": path.is_file(),
    }


def scan_live() -> dict:
    roots = []
    disk: dict = {}
    for root in LIVE_PLUGIN_ROOTS:
        row = _exists(root)
        if root.is_dir():
            found = disk_plugins(root)
            row["plugin_count"] = len(found)
            row["names"] = sorted(found)
            disk.update(found)
        else:
            row["plugin_count"] = 0
            row["names"] = []
        roots.append(row)

    listing_files = [_exists(p) for p in LIVE_LISTING_CANDIDATES]
    listing: dict = {}
    for path in LIVE_LISTING_CANDIDATES:
        if path.is_file():
            listing.update(listing_plugins(path, None))

    claude_bin = shutil.which("claude")
    skills = [_exists(p) for p in LIVE_SKILLS]
    return {
        "home": str(Path.home()),
        "claude_binary": claude_bin,
        "claude_binary_present": bool(claude_bin),
        "plugin_roots": roots,
        "disk_plugin_count": len(disk),
        "disk_names": sorted(disk),
        "listing_files": listing_files,
        "listing_plugin_count": len(listing),
        "listing_names": sorted(listing),
        "skills_trees": skills,
        "live_install_present": bool(disk) or bool(listing),
        "verdict": "ABSENT" if not disk and not listing else "PRESENT",
    }


if __name__ == "__main__":
    import json

    print(json.dumps(scan_live(), indent=2, sort_keys=True))
