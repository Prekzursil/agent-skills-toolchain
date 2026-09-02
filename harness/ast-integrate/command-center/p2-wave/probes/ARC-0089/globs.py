"""Path-glob matching for skill/rule `paths:` scopes."""
from __future__ import annotations

import re


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    pattern = pattern.replace("\\", "/")
    out: list[str] = ["^"]
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if pattern[i : i + 2] == "**":
            out.append(".*")
            i += 2
            continue
        ch = pattern[i]
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    out.append("$")
    return re.compile("".join(out))


def matches(pattern: str, rel_path: str) -> bool:
    rel = rel_path.replace("\\", "/")
    pat = pattern.replace("\\", "/")
    if pat in {"**", "**/*", "*"}:
        return True
    return glob_to_regex(pat).match(rel) is not None


def any_match(patterns: list[str], rel_path: str) -> bool:
    return any(matches(p, rel_path) for p in patterns)
