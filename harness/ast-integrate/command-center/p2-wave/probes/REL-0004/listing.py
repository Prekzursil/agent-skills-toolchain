"""File-listing check — passes whether hooks loaded or not. Disqualified as acceptance."""
from __future__ import annotations

from pathlib import Path

from package_spec import EXPECTED_RELATIVE_FILES


def listing_paths(plugin_dir: Path) -> list[str]:
    if not plugin_dir.is_dir():
        return []
    return sorted(
        p.relative_to(plugin_dir).as_posix()
        for p in plugin_dir.rglob("*")
        if p.is_file()
    )


def listing_passes(plugin_dir: Path) -> dict:
    paths = listing_paths(plugin_dir)
    missing = [rel for rel in EXPECTED_RELATIVE_FILES if rel not in paths]
    return {
        "missing": missing,
        "pass": not missing,
        "paths": paths,
        "plugin_dir": str(plugin_dir),
        "signal": "directory-listing",
    }
