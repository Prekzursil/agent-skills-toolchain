"""Scaffold marketplace package kinds (IMP-0116)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

KINDS = ("skill", "hook", "plugin", "command")

_README = """# {name}

A {kind} package.

## Usage

Run `{name}` after install.
"""

_LICENSE = "MIT License\n\nCopyright (c) 2026\n"

_SPDX = {
    "MIT": True,
    "Apache-2.0": True,
    "BSD-3-Clause": True,
}


def scaffold(
    kind: str,
    name: str,
    dest: str | Path,
    mutations: Mapping[str, Any] | None = None,
) -> Path:
    mutations = dict(mutations or {})
    root = Path(dest) / name
    root.mkdir(parents=True, exist_ok=True)
    license_id = str(mutations.get("license") or "MIT")
    manifest = {
        "id": name,
        "name": name,
        "kind": kind,
        "version": "1.0.0",
        "license": license_id,
    }
    (root / "package.json").write_text(
        __import__("json").dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (root / "README.md").write_text(_README.format(name=name, kind=kind), encoding="utf-8")
    (root / "LICENSE").write_text(_LICENSE, encoding="utf-8")
    if kind == "skill":
        (root / "SKILL.md").write_text(f"# {name}\n\nskill body\n", encoding="utf-8")
    elif kind == "hook":
        (root / "hooks.json").write_text('{"hooks": []}\n', encoding="utf-8")
    elif kind == "plugin":
        (root / "plugin.json").write_text(
            __import__("json").dumps({"id": name, "license": license_id}, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        (root / "command.md").write_text(f"# /{name}\n", encoding="utf-8")
    return root
