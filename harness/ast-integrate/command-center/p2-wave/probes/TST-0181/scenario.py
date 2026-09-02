"""Temporary plugin trees for TST-0181: with/without `$schema`, plus mutations."""
from __future__ import annotations

import json
from pathlib import Path

HOOK_SCRIPT = """\
import os
from pathlib import Path

marker_dir = Path(os.environ["HOOK_MARKER_DIR"])
marker_dir.mkdir(parents=True, exist_ok=True)
hook_id = os.environ["HOOK_ID"]
event = os.environ.get("HOOK_EVENT", "")
(marker_dir / hook_id).write_text(f"FIRED:{hook_id}:{event}\\n", encoding="utf-8")
"""

HOOKS = (
    ("pre-tool", "PreToolUse", "hooks/pre-tool.py"),
    ("post-tool", "PostToolUse", "hooks/post-tool.py"),
    ("session-start", "SessionStart", "hooks/session-start.py"),
)
SKILLS = (
    ("skill.alpha", "skills/skill.alpha/SKILL.md"),
    ("skill.beta", "skills/skill.beta/SKILL.md"),
)
SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"


def body() -> dict:
    hooks: dict[str, list[dict[str, str]]] = {}
    for hid, event, cmd in HOOKS:
        hooks.setdefault(event, []).append({"id": hid, "command": cmd})
    return {
        "hooks": hooks,
        "skills": [{"id": sid, "path": rel} for sid, rel in SKILLS],
    }


def with_schema() -> dict:
    doc = body()
    return {"$schema": SCHEMA_URI, **doc}


def without_schema() -> dict:
    return body()


def seed_tree(root: Path, *, schema: bool = True, extra: dict | None = None) -> Path:
    """Write a plugin tree. Returns the hooks.json path."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "hooks").mkdir(parents=True, exist_ok=True)
    for hid, _event, rel in HOOKS:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(HOOK_SCRIPT, encoding="utf-8")
        _ = hid
    for sid, rel in SKILLS:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {sid}\nloaded-by-tst-0181\n", encoding="utf-8")
    doc = with_schema() if schema else without_schema()
    if extra:
        doc.update(extra)
    manifest = root / "hooks.json"
    manifest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return manifest


def expected_hook_ids() -> list[str]:
    return [h[0] for h in HOOKS]


def expected_skill_ids() -> list[str]:
    return [s[0] for s in SKILLS]
