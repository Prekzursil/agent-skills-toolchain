"""Legacy layout migration steps (ADV-0060 / IMP-0049)."""
from __future__ import annotations

import shutil
from pathlib import Path

HOOK_SRC = "hooks/check.py"
HOOK_DST = "hooks/post-install.py"


def seed_legacy_tree(root: Path) -> None:
    root = Path(root)
    hook = root / HOOK_SRC
    hook.parent.mkdir(parents=True, exist_ok=True)
    if not hook.is_file():
        hook.write_text("#!/usr/bin/env python3\n# python3 hooks/check.py\n", encoding="utf-8")


def apply_hooks_dispatch(root: Path) -> None:
    """Move hooks/check.py -> hooks/post-install.py without executing it."""
    root = Path(root)
    src = root / HOOK_SRC
    dst = root / HOOK_DST
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))


FROM_VERSION = "1.0.0"
TO_VERSION = "2.0.0"
STEP_IDS = (
    "copied-skills-to-marketplace",
    "renamed-hooks-dir",
    "wrote-layout-marker",
)


def recorded_steps():
    from pathlib import Path as _P
    from typing import Any, Callable

    def _copy_skills(root: _P) -> dict[str, Any]:
        src = root / "skills"
        dest = root / "marketplace" / "skills"
        dest.mkdir(parents=True, exist_ok=True)
        entries = []
        if src.exists():
            for p in src.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(src).as_posix()
                    target = dest / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    data = p.read_bytes()
                    target.write_bytes(data)
                    entries.append({"path": f"marketplace/skills/{rel}", "bytes": list(data)})
        else:
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "alpha.md").write_bytes(b"migrated-skill\n")
            entries.append({"path": "marketplace/skills/alpha.md", "bytes": list(b"migrated-skill\n")})
        return {"kind": "delete-files", "paths": [e["path"] for e in entries], "entries": entries, "touched": ["marketplace/skills"]}

    def _rename_hooks(root: _P) -> dict[str, Any]:
        src = root / "hooks"
        dest = root / "plugin-hooks"
        entries = []
        dest.mkdir(parents=True, exist_ok=True)
        if src.exists():
            for p in list(src.rglob("*")):
                if p.is_file():
                    rel = p.relative_to(src).as_posix()
                    data = p.read_bytes()
                    (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                    (dest / rel).write_bytes(data)
                    entries.append({"path": f"hooks/{rel}", "bytes": list(data)})
                    p.unlink()
        else:
            (dest / "pre.json").write_bytes(b"{}\n")
        return {"kind": "rename-dir", "from": "hooks", "to": "plugin-hooks", "entries": entries}

    def _write_marker(root: _P) -> dict[str, Any]:
        path = root / "settings.json"
        prev = path.read_bytes() if path.is_file() else b"{}"
        path.write_bytes(b'{"layout":"v2","migrated":true}\n')
        return {"kind": "replace-file", "entries": [{"path": "settings.json", "bytes": list(prev)}], "touched": ["settings.json"]}

    return [
        (STEP_IDS[0], _copy_skills),
        (STEP_IDS[1], _rename_hooks),
        (STEP_IDS[2], _write_marker),
    ]


def seed_legacy_tree(root: Path) -> Path:  # type: ignore[no-redef]
    root = Path(root)
    (root / "skills" / "alpha").mkdir(parents=True, exist_ok=True)
    (root / "hooks").mkdir(parents=True, exist_ok=True)
    (root / "skills" / "alpha" / "SKILL.md").write_bytes(b"legacy-skill-alpha\n")
    (root / "hooks" / "pre.json").write_bytes(b'{"id":"pre"}\n')
    (root / "settings.json").write_bytes(b'{"layout":"legacy"}\n')
    hook = root / HOOK_SRC
    if not hook.is_file():
        hook.write_text("#!/usr/bin/env python3\n# python3 hooks/check.py\n", encoding="utf-8")
    return root
