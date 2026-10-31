"""Throwaway plugin-tree fixtures for set-difference rollback (IMP-0026)."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

PLUGIN_REL = Path(".claude") / "plugins" / "ast-integrate"

OWNED_V2 = (
    "commands/plugin-status.md",
    "hooks/hook.pre-tool.json",
    "plugin.json",
    "rules/rule.no-secrets.md",
    "skills/plugin-skill/SKILL.md",
)
OWNED_V1 = (
    "commands/plugin-status.md",
    "hooks/hook.pre-tool.json",
    "plugin.json",
    "rules/rule.no-secrets.md",
    "skills/core/SKILL.md",
)
FOREIGN_PATHS = (
    "commands/user-created.md",
    "skills/user-notes/SKILL.md",
    "user-data/notes.txt",
)

PAYLOAD_V2: dict[str, str] = {
    "commands/plugin-status.md": "status-v2\n",
    "hooks/hook.pre-tool.json": '{"hook":"pre-tool","v":2}\n',
    "plugin.json": '{"name":"ast-integrate","version":"2.0.0"}\n',
    "rules/rule.no-secrets.md": "rule-v2\n",
    "skills/plugin-skill/SKILL.md": "plugin-skill-v2\n",
}
PAYLOAD_V1: dict[str, str] = {
    "commands/plugin-status.md": "status-v1\n",
    "hooks/hook.pre-tool.json": '{"hook":"pre-tool","v":1}\n',
    "plugin.json": '{"name":"ast-integrate","version":"1.0.0"}\n',
    "rules/rule.no-secrets.md": "rule-v1\n",
    "skills/core/SKILL.md": "core-skill-v1\n",
}
FOREIGN: dict[str, str] = {
    "commands/user-created.md": "IMP-0026-FOREIGN-COMMAND\nuser command body\n",
    "skills/user-notes/SKILL.md": "user notes skill\n",
    "user-data/notes.txt": "private user notes\n",
}


def _write_mapping(root: Path, mapping: Mapping[str, str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for rel, body in mapping.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8", newline="\n")


def seed_payload(root: Path, mapping: Mapping[str, str]) -> Path:
    _write_mapping(root, mapping)
    return root


def seed_v2_with_foreign(home: Path) -> Path:
    live = home / PLUGIN_REL
    _write_mapping(live, {**PAYLOAD_V2, **FOREIGN})
    return live


def expected_post_v1_with_foreign() -> dict[str, str]:
    return {**PAYLOAD_V1, **FOREIGN}
