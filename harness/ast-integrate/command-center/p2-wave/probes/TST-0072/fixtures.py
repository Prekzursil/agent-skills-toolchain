#!/usr/bin/env python3
"""Disposable profile: shipped (managed) files plus user-owned files in the same tree.

User-owned paths sit inside the managed directory tree on purpose. That is the
question TST-0072 asks: tree-replace rollback is collateral by construction.
"""
from __future__ import annotations

import json
from pathlib import Path

MANAGED_V1 = {
    "VERSION": "1.0.0\n",
    "bin/tool.sh": "#!/bin/sh\necho TST-0072-tool-v1\n",
    "commands/shipped-status.md": "# shipped-status v1\nstatus-v1-body\n",
    "commands/shipped-help.md": "# shipped-help v1\nhelp-v1-body\n",
    "rules/common/agents.md": "# agents v1\nmanaged-agents-v1\n",
}

MANAGED_V2 = {
    "VERSION": "2.0.0\n",
    "bin/tool.sh": "#!/bin/sh\necho TST-0072-tool-v2\n",
    "commands/shipped-status.md": "# shipped-status v2\nstatus-v2-body\n",
    "commands/shipped-help.md": "# shipped-help v2\nhelp-v2-body\n",
    "rules/common/agents.md": "# agents v2\nmanaged-agents-v2\n",
    "commands/shipped-new.md": "# shipped-new v2-only\nupgrade-added-command\n",
}

USER_OWNED = {
    "notes/keep-me.md": "USER-UNIQUE-BYTES keep-me\nuser-notes\n",
    "commands/user-custom.md": "# user-custom\nUSER-CMD-UNIQUE\n",
    "rules/user-overlay.md": "USER-OVERLAY-UNIQUE\n",
    ".local/settings.json": "{\"theme\":\"user-owned\",\"keep\":true}\n",
}

MANIFEST_NAME = ".managed-manifest.json"


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body.encode("utf-8"))


def write_managed_manifest(root: Path, rels: list[str]) -> None:
    payload = {"managed_paths": sorted(rels), "kind": "product-owned"}
    _write(root / MANIFEST_NAME, json.dumps(payload, indent=2) + "\n")


def plant_v1(root: Path) -> list[str]:
    rels = sorted(MANAGED_V1)
    for rel, body in MANAGED_V1.items():
        _write(root / rel, body)
    write_managed_manifest(root, rels)
    return rels


def plant_user_owned(root: Path) -> list[str]:
    for rel, body in USER_OWNED.items():
        _write(root / rel, body)
    return sorted(USER_OWNED)


def upgrade_to_v2(root: Path) -> list[str]:
    rels = sorted(MANAGED_V2)
    for rel, body in MANAGED_V2.items():
        _write(root / rel, body)
    write_managed_manifest(root, rels)
    return rels


def copy_v1_snapshot(dest: Path) -> None:
    plant_v1(dest)
