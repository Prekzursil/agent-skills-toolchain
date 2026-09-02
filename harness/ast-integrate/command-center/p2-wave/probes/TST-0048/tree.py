#!/usr/bin/env python3
"""Fixture managed tree: installer files plus planted user data / commands."""
from __future__ import annotations

import json
from pathlib import Path

from ledger import default_ledger

SYNTHETIC_CREDENTIAL = (
    '{"kind":"synthetic-fixture","not_a_secret":true,'
    '"token":"TST0048.FAKE.CREDENTIAL.STORE"}\n'
)

CONTENTS_V1: dict[str, str] = {
    "plugin.json": '{"name":"harness","version":"1.0.0","managed":true}\n',
    "hooks/hook.pre-tool.json": '{"id":"hook.pre-tool","version":1}\n',
    "commands/cmd.builtin.json": '{"id":"cmd.builtin","origin":"installer"}\n',
    "skills/skill.shipped.md": "# shipped skill v1\n",
    "config/harness.json": '{"theme":"default","channel":"stable"}\n',
    "owner/hand-edit.md": "# owner authored\nKEEP-THIS-EDIT\n",
    "data/user-notes.txt": "user note planted before rollback\n",
    "settings/user-key.json": '{"favorite":"user-value","origin":"user"}\n',
    "commands/cmd.user-owned.json": '{"id":"cmd.user-owned","origin":"user"}\n',
    "skills/skill.user.md": "# user skill that pre-dated install\n",
    "mcp/curation.json": '{"servers":{"docs":"enabled","extra":"disabled"}}\n',
    "credentials/store.synthetic.json": SYNTHETIC_CREDENTIAL,
}

INSTALL_MUTATIONS: dict[str, str] = {
    "plugin.json": '{"name":"harness","version":"2.0.0","managed":true}\n',
    "skills/skill.shipped.md": "# shipped skill v2 OVERWRITTEN\n",
    "config/harness.json": '{"theme":"dark","channel":"beta"}\n',
    "hooks/hook.pre-tool.json": '{"id":"hook.pre-tool","version":2}\n',
    "plugin-extra.json": '{"created_at_install":true}\n',
}

POST_INSTALL_USER = {
    "data/user-notes-after-install.txt": "user note added AFTER install mutation\n",
}


def write_rel(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def materialize_base(root: Path) -> None:
    """Pre-install tree: installer v1 plus user-owned / pre-existing files."""
    root.mkdir(parents=True, exist_ok=True)
    for rel, text in CONTENTS_V1.items():
        write_rel(root, rel, text)


def apply_install(root: Path) -> None:
    """Mutate installer-managed files and plant a post-install user file."""
    for rel, text in INSTALL_MUTATIONS.items():
        write_rel(root, rel, text)
    for rel, text in POST_INSTALL_USER.items():
        write_rel(root, rel, text)


def scenario_meta() -> dict:
    led = default_ledger()
    return {
        "unit_id": "TST-0048",
        "creation_set": sorted(led.creation.paths),
        "preserve_set": sorted(led.preserve),
        "disjoint": True,
        "synthetic_credential_marker": "TST0048.FAKE.CREDENTIAL.STORE",
    }


def write_scenario_meta(path: Path) -> None:
    path.write_text(json.dumps(scenario_meta(), indent=2) + "\n", encoding="utf-8")
