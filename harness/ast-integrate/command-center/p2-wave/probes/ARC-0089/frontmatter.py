"""Minimal YAML-frontmatter reader for skill/rule files.

Not a full YAML parser. Supports the shapes this contract actually uses:
scalar `key: value`, a block list under `paths:`, and an inline JSON list.
"""
from __future__ import annotations

import json
import re
from typing import Any


_FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", re.DOTALL)


def split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Return (frontmatter or None if the file has no fence, body).

    A missing fence is a measured always-on document, not a parse error.
    An opened fence that never closes is a contract violation.
    """
    if not text.startswith("---"):
        return None, text
    m = _FM_RE.match(text)
    if m is None:
        raise ValueError("frontmatter-unclosed")
    raw = m.group(1)
    body = text[m.end() :]
    return parse_simple_yaml(raw), body


def parse_simple_yaml(raw: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        if line.startswith(" ") or line.startswith("\t"):
            raise ValueError(f"frontmatter-orphan-indent:{line!r}")
        if ":" not in line:
            raise ValueError(f"frontmatter-not-a-pair:{line!r}")
        key, rest = line.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        if rest == "":
            items: list[Any] = []
            i += 1
            while i < len(lines) and (
                lines[i].startswith("  ") or lines[i].startswith("\t")
            ):
                item = lines[i].strip()
                if item.startswith("- "):
                    items.append(_scalar(item[2:].strip()))
                elif item.startswith("-"):
                    items.append(_scalar(item[1:].strip()))
                else:
                    raise ValueError(f"frontmatter-bad-list-item:{item!r}")
                i += 1
            out[key] = items
            continue
        out[key] = _scalar(rest)
        i += 1
    return out


def _scalar(value: str) -> Any:
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    if value in ("null", "Null", "~"):
        return None
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = [
                _scalar(p.strip()) for p in value[1:-1].split(",") if p.strip()
            ]
        return parsed
    try:
        if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
            return int(value)
    except ValueError:
        pass
    return value


def paths_key_present(frontmatter: dict[str, Any] | None) -> bool:
    """Presence of the key, not the glob values, is the load-mode switch."""
    return isinstance(frontmatter, dict) and "paths" in frontmatter
