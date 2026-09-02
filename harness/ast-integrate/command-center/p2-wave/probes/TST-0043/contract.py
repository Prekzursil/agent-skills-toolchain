#!/usr/bin/env python3
"""Executable skill-contract checker for TST-0043.

Rules (probe1 ships one negative per rule):
  SHAPE            SKILL.md lives at skills/<name>/SKILL.md
  FRONTMATTER      closed YAML fences; unparseable YAML is malformed
  NAME             resolvable identifier, equal to the directory name
  DESCRIPTION      non-empty string the capability router can consume
  TRIGGER          explicit load class: always-on, or lazy with paths

Malformed skills must not be treated as valid. deploy.py is the loud
reject-at-deploy seam; this module only classifies.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

NAME_RE = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
LOAD_ALWAYS = "always-on"
LOAD_LAZY = "lazy"
VALID_LOAD = frozenset({LOAD_ALWAYS, LOAD_LAZY})

REASON_FRONTMATTER_ABSENT = "FRONTMATTER_ABSENT"
REASON_FRONTMATTER_UNCLOSED = "FRONTMATTER_UNCLOSED"
REASON_FRONTMATTER_UNPARSEABLE = "FRONTMATTER_UNPARSEABLE"
REASON_FRONTMATTER_EMPTY = "FRONTMATTER_EMPTY"
REASON_NAME_MISSING = "NAME_MISSING"
REASON_NAME_EMPTY = "NAME_EMPTY"
REASON_NAME_UNRESOLVABLE = "NAME_UNRESOLVABLE"
REASON_NAME_DIR_MISMATCH = "NAME_DIR_MISMATCH"
REASON_DESCRIPTION_MISSING = "DESCRIPTION_MISSING"
REASON_DESCRIPTION_EMPTY = "DESCRIPTION_EMPTY"
REASON_TRIGGER_MISSING = "TRIGGER_MISSING"
REASON_LOAD_INVALID = "LOAD_INVALID"
REASON_PATHS_MISSING_FOR_LAZY = "PATHS_MISSING_FOR_LAZY"
REASON_PATHS_EMPTY_FOR_LAZY = "PATHS_EMPTY_FOR_LAZY"
REASON_PATHS_FORBIDDEN_FOR_ALWAYS = "PATHS_FORBIDDEN_FOR_ALWAYS"
REASON_SHAPE_NOT_SKILL_MD = "SHAPE_NOT_SKILL_MD"
REASON_SHAPE_NOT_UNDER_SKILLS = "SHAPE_NOT_UNDER_SKILLS"


@dataclass
class SkillCheck:
    path: str
    skill_id: str
    ok: bool
    reasons: list[str] = field(default_factory=list)
    fields: dict[str, Any] = field(default_factory=dict)

    def primary_reason(self) -> str:
        return self.reasons[0] if self.reasons else "OK"


def _unquote(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in {"'", '"'}:
        return v[1:-1]
    return v


def _is_list_item(line: str) -> bool:
    stripped = line.lstrip(" \t")
    return (line.startswith(" ") or line.startswith("\t")) and stripped.startswith("-")


def parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse a restricted YAML frontmatter. Unsupported YAML is unparseable."""
    body = text.replace("\r\n", "\n").replace("\r", "\n")
    if not body.startswith("---\n"):
        return None, REASON_FRONTMATTER_ABSENT
    rest = body[4:]
    if rest == "---" or rest.startswith("---\n"):
        return None, REASON_FRONTMATTER_EMPTY
    end = rest.find("\n---\n")
    if end < 0:
        return None, REASON_FRONTMATTER_UNCLOSED
    block = rest[:end]
    if not block.strip():
        return None, REASON_FRONTMATTER_EMPTY
    data: dict[str, Any] = {}
    lines = block.split("\n")
    i = 0
    while i < len(lines):
        raw = lines[i]
        if raw.strip() == "":
            i += 1
            continue
        if raw.startswith(" ") or raw.startswith("\t"):
            return None, REASON_FRONTMATTER_UNPARSEABLE
        if ":" not in raw:
            return None, REASON_FRONTMATTER_UNPARSEABLE
        key, _, after = raw.partition(":")
        key = key.strip()
        if not key or " " in key:
            return None, REASON_FRONTMATTER_UNPARSEABLE
        if key in data:
            return None, REASON_FRONTMATTER_UNPARSEABLE
        after = after.strip()
        if after.startswith("[") and not after.endswith("]"):
            return None, REASON_FRONTMATTER_UNPARSEABLE
        if after.startswith("[") and after.endswith("]"):
            inner = after[1:-1].strip()
            if inner == "":
                data[key] = []
            else:
                data[key] = [_unquote(p.strip()) for p in inner.split(",")]
            i += 1
            continue
        if after in {"|", ">"}:
            return None, REASON_FRONTMATTER_UNPARSEABLE
        if after == "":
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if _is_list_item(nxt):
                items: list[str] = []
                i += 1
                while i < len(lines) and _is_list_item(lines[i]):
                    item = lines[i].lstrip(" \t")
                    if item.startswith("- "):
                        items.append(_unquote(item[2:]))
                    elif item == "-":
                        items.append("")
                    else:
                        return None, REASON_FRONTMATTER_UNPARSEABLE
                    i += 1
                data[key] = items
                continue
            data[key] = ""
            i += 1
            continue
        data[key] = _unquote(after)
        i += 1
    return data, None


def _as_str_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if not isinstance(item, str):
                return None
            out.append(item)
        return out
    if isinstance(value, str):
        return [value]
    return None


def check_skill_file(path: Path, *, tree_root: Path | None = None) -> SkillCheck:
    rel = path.as_posix()
    if tree_root is not None:
        try:
            rel = path.relative_to(tree_root).as_posix()
        except ValueError:
            rel = path.as_posix()
    skill_id = path.parent.name
    check = SkillCheck(path=rel, skill_id=skill_id, ok=True)

    if path.name != "SKILL.md":
        check.ok = False
        check.reasons.append(REASON_SHAPE_NOT_SKILL_MD)
        return check
    parts = Path(rel).parts
    if "skills" not in parts:
        check.ok = False
        check.reasons.append(REASON_SHAPE_NOT_UNDER_SKILLS)
        return check

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        check.ok = False
        check.reasons.append(REASON_FRONTMATTER_ABSENT)
        return check

    fields, parse_reason = parse_frontmatter(text)
    if parse_reason:
        check.ok = False
        check.reasons.append(parse_reason)
        return check
    assert fields is not None
    check.fields = fields

    if "name" not in fields:
        check.ok = False
        check.reasons.append(REASON_NAME_MISSING)
    else:
        name = fields["name"]
        if not isinstance(name, str) or name.strip() == "":
            check.ok = False
            check.reasons.append(REASON_NAME_EMPTY)
        elif not NAME_RE.match(name.strip()):
            check.ok = False
            check.reasons.append(REASON_NAME_UNRESOLVABLE)
        elif name.strip() != skill_id:
            check.ok = False
            check.reasons.append(REASON_NAME_DIR_MISMATCH)

    if "description" not in fields:
        check.ok = False
        check.reasons.append(REASON_DESCRIPTION_MISSING)
    else:
        desc = fields["description"]
        if not isinstance(desc, str) or desc.strip() == "":
            check.ok = False
            check.reasons.append(REASON_DESCRIPTION_EMPTY)

    if "load" not in fields:
        check.ok = False
        check.reasons.append(REASON_TRIGGER_MISSING)
    else:
        load = fields["load"]
        if not isinstance(load, str) or load not in VALID_LOAD:
            check.ok = False
            check.reasons.append(REASON_LOAD_INVALID)
        else:
            paths = _as_str_list(fields.get("paths"))
            nonempty_paths = [
                p for p in (paths or []) if isinstance(p, str) and p.strip()
            ]
            if load == LOAD_LAZY:
                if paths is None:
                    check.ok = False
                    check.reasons.append(REASON_PATHS_MISSING_FOR_LAZY)
                elif not nonempty_paths:
                    check.ok = False
                    check.reasons.append(REASON_PATHS_EMPTY_FOR_LAZY)
            elif load == LOAD_ALWAYS and nonempty_paths:
                check.ok = False
                check.reasons.append(REASON_PATHS_FORBIDDEN_FOR_ALWAYS)

    return check


def discover_skill_files(tree_root: Path) -> list[Path]:
    skills = tree_root / "skills"
    if not skills.is_dir():
        return []
    return sorted(p for p in skills.glob("*/SKILL.md") if p.is_file())


def check_tree(tree_root: Path) -> list[SkillCheck]:
    return [
        check_skill_file(p, tree_root=tree_root) for p in discover_skill_files(tree_root)
    ]
