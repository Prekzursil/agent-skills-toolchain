#!/usr/bin/env python3
"""GitHub Actions path-filter matcher and workflow `on:` extractor.

GitHub path filters are glob patterns from the repo root (not gitignore):
  *   matches any run of characters except /
  **  matches any run of characters including /
  ?   matches one character except /
A leading ! in a list entry negates that pattern (last match wins).

YAML 1.1 parses the bare key `on:` as boolean True. Reading only doc['on']
would report every workflow as trigger-less — the same detector failure
AUD-0041 already named. extract_on() reads both keys.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

AUTO_EVENTS = frozenset(
    {
        "push",
        "pull_request",
        "pull_request_target",
        "merge_group",
    }
)


def github_glob_match(pattern: str, path: str) -> bool:
    """Return True if path matches a GitHub Actions path-filter glob."""
    pattern = (pattern or "").replace("\\", "/").lstrip("/")
    # shard4-w4 fix 2026-10-26: lstrip("./") is a CHARACTER-SET strip and
    # corrupted every dotfile path (".gitattributes" -> "gitattributes") while
    # the pattern kept its leading dot, so a literal self-match failed and the
    # evaluator recorded a FALSE live miss for the EOL gate. GitHub matches
    # dotfiles: strip only a leading "./" prefix, then a leading "/".
    path = (path or "").replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    path = path.lstrip("/")
    if not pattern:
        return False
    rx: list[str] = ["^"]
    i = 0
    n = len(pattern)
    while i < n:
        if pattern.startswith("**/", i):
            rx.append("(?:.*/)?")
            i += 3
            continue
        if pattern.startswith("**", i):
            rx.append(".*")
            i += 2
            continue
        ch = pattern[i]
        if ch == "*":
            rx.append("[^/]*")
        elif ch == "?":
            rx.append("[^/]")
        else:
            rx.append(re.escape(ch))
        i += 1
    rx.append("$")
    return re.match("".join(rx), path) is not None


def list_match(patterns: Iterable[str], path: str) -> bool:
    """gitignore-style last-match-wins over a paths / paths-ignore list."""
    matched = False
    any_positive = False
    for raw in patterns or []:
        pat = str(raw).strip()
        if not pat:
            continue
        if pat.startswith("!"):
            if github_glob_match(pat[1:], path):
                matched = False
            continue
        any_positive = True
        if github_glob_match(pat, path):
            matched = True
    if not any_positive and not matched:
        return False
    return matched


def as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            if item is None:
                continue
            out.append(str(item))
        return out
    return [str(value)]


def extract_on(doc: dict[str, Any] | None) -> Any:
    if not isinstance(doc, dict):
        return None
    if "on" in doc:
        return doc["on"]
    if True in doc:
        return doc[True]
    return None


def event_filters(on_block: Any) -> list[dict[str, Any]]:
    """Normalize workflow `on:` into per-event path filter records."""
    events: list[dict[str, Any]] = []
    if on_block is None:
        return events
    if isinstance(on_block, str):
        return [
            {
                "event": on_block,
                "paths": [],
                "paths-ignore": [],
                "has_path_filter": False,
            }
        ]
    if isinstance(on_block, list):
        for item in on_block:
            if isinstance(item, str):
                events.append(
                    {
                        "event": item,
                        "paths": [],
                        "paths-ignore": [],
                        "has_path_filter": False,
                    }
                )
        return events
    if not isinstance(on_block, dict):
        return events
    for event, cfg in on_block.items():
        name = str(event)
        if cfg is None or cfg is True:
            paths: list[str] = []
            ignore: list[str] = []
        elif isinstance(cfg, dict):
            paths = as_str_list(cfg.get("paths"))
            ignore = as_str_list(cfg.get("paths-ignore"))
        else:
            paths, ignore = [], []
        events.append(
            {
                "event": name,
                "paths": paths,
                "paths-ignore": ignore,
                "has_path_filter": bool(paths or ignore),
            }
        )
    return events


def would_run(event: dict[str, Any], changed_files: Iterable[str]) -> bool:
    """Whether GitHub would run this event given the changed file set.

    paths: at least one changed file must match.
    paths-ignore: skipped only when every changed file matches an ignore pattern.
    Both: both conditions must hold.
    """
    # shard4-w4 fix 2026-10-26: same character-set-strip defect as
    # github_glob_match - lstrip("./") corrupted dotfile paths; strip only a
    # leading "./" prefix (repeatedly), never the dot itself.
    files = []
    for f in changed_files:
        if not f:
            continue
        f = str(f).replace("\\", "/")
        while f.startswith("./"):
            f = f[2:]
        files.append(f.lstrip("/"))
    if not files:
        return False
    paths = event.get("paths") or []
    ignore = event.get("paths-ignore") or []
    if not paths and not ignore:
        return True
    if paths and not any(list_match(paths, f) for f in files):
        return False
    if ignore and all(list_match(ignore, f) for f in files):
        return False
    return True


def single_file_miss(event: dict[str, Any], protected_file: str) -> bool:
    """True when a one-file commit of protected_file would not run the event."""
    if not event.get("has_path_filter"):
        return False
    return not would_run(event, [protected_file])
