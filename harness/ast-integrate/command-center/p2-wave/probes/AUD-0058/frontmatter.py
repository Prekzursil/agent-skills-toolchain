"""Minimal YAML-frontmatter reader for skill/rule files.

Presence of the `paths` key — not glob values — is the load-mode switch.
A missing fence is always-on, not a parse error.
"""
from __future__ import annotations

import json
import re
from typing import Any

_FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", re.DOTALL)


def split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    if not text.startswith("---"):
        return None, text
    m = _FM_RE.match(text)
    if m is None:
        raise ValueError("frontmatter-unclosed")
    return parse_simple_yaml(m.group(1)), text[m.end() :]


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
            # YAML allows a block sequence (items indented under the key or
            # flush-left at the key's column) or a nested block mapping.
            block: list[str] = []
            i += 1
            while i < len(lines) and (
                lines[i].startswith("  ")
                or lines[i].startswith("\t")
                or lines[i].startswith("- ")
                or lines[i].rstrip() == "-"
                or not lines[i].strip()
            ):
                if lines[i].strip():
                    block.append(lines[i].strip())
                i += 1
            if block and not block[0].startswith("-"):
                nested: dict[str, Any] = {}
                last: str | None = None
                for item in block:
                    if item.startswith("-"):
                        val = _scalar(item[1:].strip())
                        if last is None:
                            raise ValueError(
                                f"frontmatter-bad-mapping-item:{item!r}"
                            )
                        cur = nested.get(last)
                        if isinstance(cur, list):
                            cur.append(val)
                        elif cur in (None, "", [], {}):
                            nested[last] = [val]
                        else:
                            nested[last] = [cur, val]
                    elif ":" in item:
                        k2, v2 = item.split(":", 1)
                        last = k2.strip()
                        v2 = v2.strip()
                        nested[last] = _scalar(v2) if v2 else ""
                    elif last is not None and isinstance(nested.get(last), str):
                        nested[last] = (nested[last] + " " + item).strip()
                    else:
                        raise ValueError(f"frontmatter-bad-mapping-item:{item!r}")
                out[key] = nested
                continue
            items: list[Any] = []
            for item in block:
                if item.startswith("- "):
                    items.append(_scalar(item[2:].strip()))
                elif item.startswith("-"):
                    items.append(_scalar(item[1:].strip()))
                else:
                    raise ValueError(f"frontmatter-bad-list-item:{item!r}")
            out[key] = items
            continue
        if rest in ("|", ">", "|-", ">-", "|+", ">+"):
            # Block scalar: consume the indented block into a string.
            block_lines: list[str] = []
            i += 1
            while i < len(lines) and (
                lines[i].startswith("  ")
                or lines[i].startswith("\t")
                or not lines[i].strip()
            ):
                block_lines.append(lines[i].strip())
                i += 1
            joiner = "\n" if rest.startswith("|") else " "
            out[key] = joiner.join(block_lines).strip()
            continue
        value = _scalar(rest)
        i += 1
        # YAML plain scalars may wrap onto indented continuation lines.
        while (
            isinstance(value, str)
            and i < len(lines)
            and (lines[i].startswith("  ") or lines[i].startswith("\t"))
            and lines[i].strip()
            and not lines[i].strip().startswith("- ")
        ):
            value = value + " " + lines[i].strip()
            i += 1
        out[key] = value
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
    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)
    return value


def paths_key_present(frontmatter: dict[str, Any] | None) -> bool:
    return isinstance(frontmatter, dict) and "paths" in frontmatter
