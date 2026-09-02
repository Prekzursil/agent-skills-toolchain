#!/usr/bin/env python3
"""CycloneDX emitter for REL-0011.

Tool A. Reads declared sources only:
  * npm package-lock.json `packages` key enumeration (not a graph walk)
  * python-requirements.lock column-0 name==version lines
  * vendor-manifest.json declared vendored entries

Does not walk vendor/ on disk and does not BFS the lockfile dependency graph.
Those are the resolver's job. Generation alone is not the gate.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

TOOL_NAME = "rel0011-cyclonedx-emitter"
TOOL_KIND = "cyclonedx-declared-source-emitter"
TOOL_VERSION = "1.0.0"

_PIP_PIN = re.compile(r"^([A-Za-z0-9_.-]+)==(\S+)")


def _npm_name_from_location(loc: str, meta: dict) -> str:
    named = str(meta.get("name") or "").strip()
    if named:
        return named
    parts = loc.replace("\\", "/").split("node_modules/")
    return parts[-1] if parts else loc


def emit_from_lockfile_keys(lock: dict) -> list[dict]:
    """Enumerate packages map keys. Deliberately not a graph walk."""
    out: list[dict] = []
    packages = lock.get("packages") if isinstance(lock, dict) else None
    if not isinstance(packages, dict):
        return out
    for loc, meta in packages.items():
        if loc in ("", "."):
            continue
        if not isinstance(meta, dict):
            continue
        name = _npm_name_from_location(str(loc), meta)
        version = str(meta.get("version") or "").strip()
        if not name or not version:
            continue
        purl = f"pkg:npm/{name}@{version}"
        out.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": purl,
                "bom-ref": purl,
                "scope": "required",
                "properties": [
                    {"name": "rel0011:source", "value": "package-lock.json:packages-key"}
                ],
            }
        )
    return out


def emit_from_pip_column0(text: str) -> list[dict]:
    """Only column-0 pins. Ignores via-comments (resolver records via-depth)."""
    out: list[dict] = []
    for line in text.splitlines():
        if line.startswith((" ", "\t")):
            continue
        m = _PIP_PIN.match(line.strip())
        if not m:
            continue
        name, version = m.group(1), m.group(2)
        purl = f"pkg:pypi/{name}@{version}"
        out.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": purl,
                "bom-ref": purl,
                "scope": "required",
                "properties": [
                    {"name": "rel0011:source", "value": "python-requirements.lock:column-0"}
                ],
            }
        )
    return out


def emit_from_vendor_manifest(root: Path) -> list[dict]:
    """Declared vendored components only. Does not os.walk vendor/."""
    man_path = root / "vendor-manifest.json"
    if not man_path.is_file():
        return []
    man = json.loads(man_path.read_text(encoding="utf-8"))
    out: list[dict] = []
    for row in man.get("components") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        version = str(row.get("version") or "").strip()
        if not name or not version:
            continue
        purl = f"pkg:generic/{name}@{version}"
        out.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": purl,
                "bom-ref": purl,
                "scope": "required",
                "properties": [
                    {
                        "name": "rel0011:source",
                        "value": "vendor-manifest.json",
                    },
                    {
                        "name": "rel0011:declared-path",
                        "value": str(row.get("path") or ""),
                    },
                ],
            }
        )
    return out


def generate(release_root: Path) -> dict[str, Any]:
    root = Path(release_root)
    components: list[dict] = []
    lock_path = root / "package-lock.json"
    if lock_path.is_file():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        components.extend(emit_from_lockfile_keys(lock))
        app_name = str(lock.get("name") or "ast-release")
        app_ver = str(lock.get("version") or "0.0.0")
    else:
        pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
        app_name = str(pkg.get("name") or "ast-release")
        app_ver = str(pkg.get("version") or "0.0.0")
    pip_path = root / "python-requirements.lock"
    if pip_path.is_file():
        components.extend(emit_from_pip_column0(pip_path.read_text(encoding="utf-8")))
    components.extend(emit_from_vendor_manifest(root))
    components.sort(key=lambda c: str(c.get("purl") or ""))
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:rel-0011-ast-release-fixture",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": app_name,
                "version": app_ver,
                "bom-ref": f"pkg:generic/{app_name}@{app_ver}",
            },
            "tools": {
                "components": [
                    {
                        "type": "application",
                        "name": TOOL_NAME,
                        "version": TOOL_VERSION,
                    }
                ]
            },
        },
        "components": components,
    }


def bill_purls(bom: dict) -> list[str]:
    out = []
    for c in bom.get("components") or []:
        if isinstance(c, dict) and c.get("purl"):
            out.append(str(c["purl"]))
    return sorted(out)


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    json.dump(generate(target), sys.stdout, indent=2)
    sys.stdout.write("\n")
