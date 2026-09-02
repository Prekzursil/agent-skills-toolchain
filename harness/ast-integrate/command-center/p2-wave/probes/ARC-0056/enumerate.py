"""Walk the live command/skill/monitor/script trees. Names come from files."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

KIND_SLASH = "slash-command"
KIND_SKILL = "skill"
KIND_MONITOR = "monitor"
KIND_SCRIPT = "ad-hoc-script"

_FM = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_KV = re.compile(r"^([A-Za-z0-9_]+):\s*(.+?)\s*$", re.MULTILINE)
_SCRIPT_NAME = re.compile(r"(?m)^(?:#|//)\s*name:\s*(\S+)\s*$")


def _frontmatter(text: str) -> dict[str, str]:
    m = _FM.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for km in _KV.finditer(m.group(1)):
        out[km.group(1)] = km.group(2).strip().strip('"').strip("'")
    return out


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def enumerate_live(live_root: Path) -> list[dict[str, Any]]:
    """Return one row per live name, sorted by (kind, name). Fail closed on parse."""
    live_root = live_root.resolve()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    commands = live_root / "commands"
    if not commands.is_dir():
        raise FileNotFoundError(f"missing commands tree: {commands}")
    for path in sorted(commands.glob("*.md")):
        meta = _frontmatter(_read(path))
        name = meta.get("name") or ""
        kind = meta.get("kind") or KIND_SLASH
        if not name.startswith("/") or kind != KIND_SLASH:
            raise ValueError(f"unparseable slash command {path}")
        rel = path.relative_to(live_root).as_posix()
        rows.append({"name": name, "kind": kind, "path": rel})

    skills = live_root / "skills"
    if not skills.is_dir():
        raise FileNotFoundError(f"missing skills tree: {skills}")
    for path in sorted(skills.glob("*/SKILL.md")):
        meta = _frontmatter(_read(path))
        name = meta.get("name") or ""
        kind = meta.get("kind") or KIND_SKILL
        if not name.startswith("skill.") or kind != KIND_SKILL:
            raise ValueError(f"unparseable skill {path}")
        rel = path.relative_to(live_root).as_posix()
        rows.append({"name": name, "kind": kind, "path": rel})

    monitors = live_root / "monitors"
    if not monitors.is_dir():
        raise FileNotFoundError(f"missing monitors tree: {monitors}")
    for path in sorted(monitors.glob("*.json")):
        doc = json.loads(_read(path))
        name = str(doc.get("name") or doc.get("id") or "")
        kind = str(doc.get("kind") or KIND_MONITOR)
        if not name.startswith("monitor.") or kind != KIND_MONITOR:
            raise ValueError(f"unparseable monitor {path}")
        rel = path.relative_to(live_root).as_posix()
        rows.append({"name": name, "kind": kind, "path": rel})

    scripts = live_root / "scripts"
    if not scripts.is_dir():
        raise FileNotFoundError(f"missing scripts tree: {scripts}")
    for path in sorted(scripts.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        text = _read(path)
        m = _SCRIPT_NAME.search(text)
        name = m.group(1) if m else ""
        expect = f"scripts/{path.name}"
        if name != expect:
            raise ValueError(f"unparseable script {path} name={name!r}")
        rel = path.relative_to(live_root).as_posix()
        rows.append({"name": name, "kind": KIND_SCRIPT, "path": rel})

    for row in rows:
        n = row["name"]
        if n in seen:
            raise ValueError(f"duplicate live name {n}")
        seen.add(n)
    rows.sort(key=lambda r: (r["kind"], r["name"]))
    return rows


def by_kind(rows: list[dict[str, Any]]) -> dict[str, int]:
    out = {KIND_SLASH: 0, KIND_SKILL: 0, KIND_MONITOR: 0, KIND_SCRIPT: 0}
    for row in rows:
        out[row["kind"]] = out.get(row["kind"], 0) + 1
    return out
