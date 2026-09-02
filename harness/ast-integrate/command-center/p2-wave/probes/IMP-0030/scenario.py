"""Shared IMP-0030 fixture tree: plugin-owned files plus a planted control secret."""
from __future__ import annotations

import json
from pathlib import Path

# Distinctive synthetic body. Never print this in reports or probe stdout.
# Tests search for this string IN reports and require zero hits.
PLANTED_BODY = "SYNTHETIC_IMP0030_CONTROL_BODY_NOT_A_REAL_SECRET_9f3a7c"

PROJECTION = {
    "schema_version": 1,
    "id": "imp0030-fixture-projection",
    "entries": [
        {
            "manifest_id": "skill.alpha",
            "kind": "skill",
            "live_path": "skills/skill.alpha",
        },
        {
            "manifest_id": "hook.pre-tool",
            "kind": "hook",
            "live_path": "hooks",
        },
        {
            "manifest_id": "rule.no-secrets",
            "kind": "rule",
            "live_path": "rules/rule.no-secrets.md",
        },
        {
            "manifest_id": "settings",
            "kind": "settings",
            "live_path": "settings.json",
        },
    ],
}

SKILL_BYTES = b"name: skill.alpha\nversion: 1\nbody: unique-line-A\n"
HOOK_BYTES = b'{"id":"pre-tool","on":"PreToolUse"}\r\n'
RULE_BYTES = b"Do not embed credentials in generated files.\n"
SETTINGS_BYTES = b'{"theme":"dark","unique":"pre-op-settings"}\n'
PLANTED_REL = "skills/skill.alpha/.env"
PLANTED_NAME = "API_KEY"


def write_projection(path: Path) -> Path:
    path.write_text(json.dumps(PROJECTION, indent=2) + "\n", encoding="utf-8")
    return path


def build_live_tree(root: Path, *, plant_secret: bool) -> Path:
    """Create a throwaway live tree. Binary-ish and CRLF files prove byte identity."""
    root = Path(root)
    (root / "skills/skill.alpha").mkdir(parents=True, exist_ok=True)
    (root / "hooks").mkdir(parents=True, exist_ok=True)
    (root / "rules").mkdir(parents=True, exist_ok=True)
    (root / "skills/skill.alpha/SKILL.md").write_bytes(SKILL_BYTES)
    (root / "hooks/hook.pre-tool.json").write_bytes(HOOK_BYTES)
    (root / "rules/rule.no-secrets.md").write_bytes(RULE_BYTES)
    (root / "settings.json").write_bytes(SETTINGS_BYTES)
    # A file that is NOT in the projection and must never appear in the snapshot.
    (root / "unrelated-user-notes.txt").write_bytes(b"user-authored; not a lifecycle path\n")
    if plant_secret:
        (root / PLANTED_REL).write_bytes(
            f"{PLANTED_NAME}={PLANTED_BODY}\n".encode("ascii")
        )
    write_projection(root / "projection.json")
    return root
