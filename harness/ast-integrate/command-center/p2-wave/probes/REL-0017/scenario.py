#!/usr/bin/env python3
"""Captured hand-managed vs plugin-managed layouts for REL-0017.

The capture is a synthetic estate snapshot, not the owner's live profile.
Host ~/.claude and ~/.cursor trees are not read. The frozen capture lives
under fixtures/captured/; every conversion runs on a copy of that capture.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPTURED = HERE / "fixtures" / "captured"
HAND = CAPTURED / "hand"
PLUGIN = CAPTURED / "plugin"

PLANTED_LINE = "OWNER-AUTHORED:REL-0017-planted-do-not-destroy"
PLANTED_SOURCE = "skills/owner-skill.md"
PLANTED_TARGET = "skills/owner-skill/SKILL.md"
EOL_REL = "rules/rule.no-secrets.md"
BOTH_UNIQUE_REL = "rules/rule.security.md"
SOURCE_ONLY_RULE = "rules/rule.owner-local.md"
PLUGIN_ONLY_RULE = "rules/rule.plugin-only.md"
HAND_UNIQUE_LINE = "HAND-UNIQUE: do not clobber this operator note."
PLUGIN_UNIQUE_LINE = "PLUGIN-UNIQUE: packaged policy line."

SKILL_COUNCIL = (
    "---\n"
    "name: skill.council\n"
    "description: Council skill for the harness control plane\n"
    "---\n"
    "Roles: reviewer\n"
    "Council body shared by hand layout and plugin package.\n"
)
OWNER_SKILL = (
    "---\n"
    "name: owner-skill\n"
    "description: Owner-authored live skill planted as a destroy-me control\n"
    "---\n"
    "Roles: owner\n"
    f"{PLANTED_LINE}\n"
)
RULE_NO_SECRETS_LF = "# No secrets\nDo not print API keys.\n"
RULE_NO_SECRETS_CRLF = "# No secrets\r\nDo not print API keys.\r\n"
RULE_SECURITY_HAND = (
    "# Security\n"
    f"{HAND_UNIQUE_LINE}\n"
    "SHARED: fail closed on missing evidence.\n"
)
RULE_SECURITY_PLUGIN = (
    "# Security\n"
    f"{PLUGIN_UNIQUE_LINE}\n"
    "SHARED: fail closed on missing evidence.\n"
)
RULE_OWNER_LOCAL = (
    "# Owner local\n"
    "Live-only rule. Conversion must preserve these bytes or refuse.\n"
)
RULE_PLUGIN_ONLY = (
    "# Plugin only\n"
    "Exists only in the package. Conversion must not delete it.\n"
)
PRE_TOOL_SH = "#!/bin/sh\necho REL-0017-pre-tool\n"
OWNER_HOOK_SH = "#!/bin/sh\necho REL-0017-owner-local-hook\n"

HOOK_PRE_TOOL = {
    "id": "hook.pre-tool",
    "event": "PreToolUse",
    "script": "hooks/pre-tool.sh",
    "enabled": True,
}
HOOK_OWNER = {
    "id": "hook.owner-local",
    "event": "Stop",
    "script": "hooks/owner-local.sh",
    "enabled": True,
}


def dump_json(obj: object) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode(
        "utf-8"
    )


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_text(path: Path, text: str, *, newline: str = "\n") -> None:
    body = text.replace("\r\n", "\n").replace("\r", "\n")
    if newline == "\r\n":
        body = body.replace("\n", "\r\n")
        write_bytes(path, body.encode("utf-8"))
        return
    write_bytes(path, body.encode("utf-8"))


def wipe(root: Path) -> None:
    if not root.exists():
        return
    for p in sorted(root.rglob("*"), reverse=True):
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            try:
                p.rmdir()
            except OSError:
                pass


def build_captured() -> dict[str, str]:
    """Write the frozen captured copy. Never the live tree."""
    wipe(CAPTURED)
    HAND.mkdir(parents=True, exist_ok=True)
    PLUGIN.mkdir(parents=True, exist_ok=True)

    write_text(HAND / "skills" / "skill.council.md", SKILL_COUNCIL)
    write_text(HAND / "skills" / "owner-skill.md", OWNER_SKILL)
    write_bytes(HAND / "hooks.json", dump_json([HOOK_PRE_TOOL, HOOK_OWNER]))
    write_text(HAND / "hooks" / "pre-tool.sh", PRE_TOOL_SH)
    write_text(HAND / "hooks" / "owner-local.sh", OWNER_HOOK_SH)
    write_bytes(HAND / EOL_REL, RULE_NO_SECRETS_CRLF.encode("utf-8"))
    write_text(HAND / BOTH_UNIQUE_REL, RULE_SECURITY_HAND)
    write_text(HAND / SOURCE_ONLY_RULE, RULE_OWNER_LOCAL)

    write_text(PLUGIN / "skills" / "skill.council" / "SKILL.md", SKILL_COUNCIL)
    write_bytes(PLUGIN / "hooks" / "hook.pre-tool.json", dump_json(HOOK_PRE_TOOL))
    write_text(PLUGIN / "hooks" / "pre-tool.sh", PRE_TOOL_SH)
    write_bytes(PLUGIN / EOL_REL, RULE_NO_SECRETS_LF.encode("utf-8"))
    write_text(PLUGIN / BOTH_UNIQUE_REL, RULE_SECURITY_PLUGIN)
    write_text(PLUGIN / PLUGIN_ONLY_RULE, RULE_PLUGIN_ONLY)
    write_bytes(
        PLUGIN / "plugin.json",
        dump_json(
            {
                "name": "harness",
                "version": "1.0.0",
                "description": "Plugin-managed layout for REL-0017 rehearsal",
                "skills": ["skills/skill.council/SKILL.md"],
                "hooks": ["hooks/hook.pre-tool.json"],
                "rules": [
                    "rules/rule.no-secrets.md",
                    "rules/rule.security.md",
                    "rules/rule.plugin-only.md",
                ],
            }
        ),
    )
    return {
        "hand": str(HAND),
        "plugin": str(PLUGIN),
        "planted_source": PLANTED_SOURCE,
        "planted_target": PLANTED_TARGET,
        "planted_line": PLANTED_LINE,
    }


if __name__ == "__main__":
    meta = build_captured()
    print(json.dumps(meta, indent=2))
