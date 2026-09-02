"""Disposable snapshot: package payload plus a seeded live/user/legacy tree."""
from __future__ import annotations

from pathlib import Path

SNAPSHOT_FILES = {
    "package/plugin.json": '{"name":"cnf-0036-fixture","version":"1"}\n',
    "package/skills/hello.md": "# hello\nfixture-skill\n",
    "package/rules/rule.md": "# rule\nno-secrets\n",
    "package/hooks/hook.json": '{"event":"pre-tool","id":"hook.pre-tool"}\n',
    "target/user/notes.md": "KEEP-ME-UNIQUE-BYTES\nuser-owned-notes\n",
    "target/live/user-edit.md": "LIVE-UNIQUE-LINE\noperator-hotpatch\n",
    "target/legacy/skills/old.md": "legacy-skill-body\n",
    "target/.layout-version": "v1\n",
}

USER_NOTES = "target/user/notes.md"
USER_NOTES_BODY = SNAPSHOT_FILES[USER_NOTES]


def build_snapshot(root: Path) -> Path:
    for rel, body in SNAPSHOT_FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8", newline="\n")
    return root
