"""In-memory plugin package builder used by IMP-0087 probes."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Package:
    name: str
    version: str
    files: dict[str, bytes] = field(default_factory=dict)
    permissions: list[str] = field(default_factory=list)
    releases: list[str] = field(default_factory=list)
    changelog: dict[str, list[str]] = field(default_factory=dict)


def make_package(
    name: str,
    version: str,
    extra_files: dict[str, bytes] | None = None,
    permissions: list[str] | None = None,
    releases: list[str] | None = None,
    changelog: dict[str, list[str]] | None = None,
) -> Package:
    files = {
        "plugin.json": (
            '{"name":"%s","version":"%s","permissions":%s}\n'
            % (name, version, __import__("json").dumps(list(permissions or [])))
        ).encode("utf-8")
    }
    for rel, data in (extra_files or {}).items():
        files[rel.replace("\\", "/")] = data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")
    return Package(
        name=name,
        version=version,
        files=files,
        permissions=list(permissions or []),
        releases=list(releases or [version]),
        changelog=dict(changelog or {}),
    )
