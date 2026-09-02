"""Build a tiny verified payload for IMP-0127 probes."""

from __future__ import annotations

import json
from pathlib import Path


def build_demo_payload(root: Path, *, name: str = "handoff-demo") -> Path:
    payload = root / "payload"
    (payload / "skills" / "skill.demo").mkdir(parents=True)
    (payload / "rules").mkdir(parents=True)
    (payload / "hooks").mkdir(parents=True)
    (payload / "plugin.json").write_text(
        json.dumps(
            {
                "name": name,
                "version": "1.0.0",
                "description": "IMP-0127 probe fixture",
                "permissions": [f"fs:write:plugins/{name}"],
                "skills": ["skills/skill.demo/SKILL.md"],
                "rules": ["rules/rule.demo.md"],
                "hooks": ["hooks/hook.demo.json"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (payload / "skills" / "skill.demo" / "SKILL.md").write_text(
        "# demo skill\nTyped handoff only.\n", encoding="utf-8"
    )
    (payload / "rules" / "rule.demo.md").write_text(
        "# demo rule\nOne installer control plane.\n", encoding="utf-8"
    )
    (payload / "hooks" / "hook.demo.json").write_text(
        json.dumps({"event": "pre-tool", "enabled": True}) + "\n", encoding="utf-8"
    )
    return payload
