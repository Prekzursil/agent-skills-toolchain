#!/usr/bin/env python3
"""Extract CLI flags, config keys, and repo-relative paths from docs and code."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Iterable

FLAG_TOKEN = re.compile(r"(?<![A-Za-z0-9-])(--[A-Za-z0-9][A-Za-z0-9-]*|-[A-Za-z])(?![A-Za-z0-9-])")
LONG_FLAG = re.compile(r"^--[A-Za-z0-9][A-Za-z0-9-]*$")
SHORT_FLAG = re.compile(r"^-[A-Za-z]$")
KEY_BULLET = re.compile(r"^[-*]\s+`([A-Za-z_][A-Za-z0-9_.-]*)`")
BACKTICK = re.compile(r"`([^`]+)`")
MENTION_LINE = re.compile(
    r"(?i)removed in v\d|deprecated|do not use|no longer (accepted|supported|a live)|"
    r"was deleted|not a live (flag|key|path)|example of what not|must not count"
)
REMOVED_HEADING = re.compile(
    r"(?i)^(#{1,6}\s+)?(removed|deprecated|do not use|what not to do)\b"
)
PATHISH = re.compile(
    r"^(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+(?:\.[A-Za-z0-9]+)?$"
    r"|^[A-Za-z0-9_.-]+\.(?:py|json|md|yml|yaml|toml|txt|schema\.json)$"
)
CODE_PATH_PREFIX = ("command-center/", "tools/", "schema/")
BUILTIN_HELP = frozenset({"-h", "--help"})


def _is_flag(token: str) -> bool:
    return bool(LONG_FLAG.match(token) or SHORT_FLAG.match(token))


def add_help_enabled(source: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return True
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name not in {"ArgumentParser", "argparse.ArgumentParser"} and name != "ArgumentParser":
            continue
        for kw in node.keywords:
            if kw.arg == "add_help" and isinstance(kw.value, ast.Constant):
                return bool(kw.value.value)
    return True


def flags_from_parser_source(source: str) -> set[str]:
    """AST: option strings passed to add_argument / add_parser."""
    flags: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return flags
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        attr = func.attr if isinstance(func, ast.Attribute) else None
        if attr not in {"add_argument", "add_parser"}:
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and _is_flag(arg.value):
                flags.add(arg.value)
    if add_help_enabled(source):
        flags -= BUILTIN_HELP
    return flags


def code_paths_from_parser_source(source: str) -> set[str]:
    """Repo-relative path strings used as argparse defaults."""
    paths: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return paths
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        attr = func.attr if isinstance(func, ast.Attribute) else None
        if attr != "add_argument":
            continue
        for kw in node.keywords:
            if kw.arg != "default":
                continue
            val = kw.value
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                text = val.value.replace("\\", "/")
                if any(text.startswith(p) for p in CODE_PATH_PREFIX) or PATHISH.match(text):
                    if not text.startswith("-") and "http" not in text:
                        paths.add(text)
    return paths


def _mention_mask(text: str) -> list[bool]:
    """True when a line is a use-vs-mention (removed / do-not-use) region."""
    lines = text.splitlines()
    mask = [False] * len(lines)
    in_removed_fence = False
    in_removed_section = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            info = stripped[3:].strip().lower()
            if not in_removed_fence:
                in_removed_fence = any(
                    tok in info for tok in ("removed", "deprecated", "bad-example", "do-not")
                )
            else:
                in_removed_fence = False
            mask[i] = True
            continue
        if REMOVED_HEADING.match(stripped):
            in_removed_section = True
        elif stripped.startswith("#") and in_removed_section:
            in_removed_section = False
        if in_removed_fence or in_removed_section or MENTION_LINE.search(line):
            mask[i] = True
    return mask


def flags_from_docs(text: str) -> tuple[set[str], set[str]]:
    """Return (live documented flags, mention-only flags)."""
    live: set[str] = set()
    mentions: set[str] = set()
    mask = _mention_mask(text)
    for i, line in enumerate(text.splitlines()):
        found = {m.group(0) for m in FLAG_TOKEN.finditer(line) if _is_flag(m.group(0))}
        found -= BUILTIN_HELP
        if mask[i]:
            mentions |= found
        else:
            live |= found
    mentions -= live
    return live, mentions


def keys_from_schema(doc: object, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if not isinstance(doc, dict):
        return keys
    props = doc.get("properties")
    if isinstance(props, dict):
        for name, sub in props.items():
            dotted = name if not prefix else f"{prefix}.{name}"
            keys.add(name)
            keys.add(dotted)
            keys |= keys_from_schema(sub, dotted)
    for combo in ("oneOf", "anyOf", "allOf"):
        items = doc.get(combo)
        if isinstance(items, list):
            for item in items:
                keys |= keys_from_schema(item, prefix)
    for nest in ("items", "additionalProperties"):
        sub = doc.get(nest)
        if isinstance(sub, dict):
            keys |= keys_from_schema(sub, prefix)
    return keys


def keys_from_docs(text: str) -> tuple[set[str], set[str]]:
    live: set[str] = set()
    mentions: set[str] = set()
    mask = _mention_mask(text)
    in_json = False
    json_lines: list[str] = []
    for i, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith("```"):
            info = stripped[3:].strip().lower()
            if not in_json:
                in_json = info in {"json", "yaml", "yml"}
                json_lines = []
            else:
                blob = "\n".join(json_lines)
                try:
                    parsed = json.loads(blob)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    target = mentions if any(mask[j] for j in range(max(0, i - len(json_lines)), i)) else live
                    target |= {k for k in parsed.keys() if isinstance(k, str)}
                in_json = False
            continue
        if in_json:
            json_lines.append(line)
            continue
        m = KEY_BULLET.match(stripped)
        if m:
            (mentions if mask[i] else live).add(m.group(1))
    return live, mentions


def paths_from_docs(text: str) -> tuple[set[str], set[str]]:
    live: set[str] = set()
    mentions: set[str] = set()
    mask = _mention_mask(text)
    for i, line in enumerate(text.splitlines()):
        for raw in BACKTICK.findall(line):
            token = raw.replace("\\", "/").strip()
            if token.startswith("http") or _is_flag(token):
                continue
            if PATHISH.match(token):
                (mentions if mask[i] else live).add(token)
    return live, mentions


def diff(documented: Iterable[str], implemented: Iterable[str]) -> dict:
    doc = set(documented)
    impl = set(implemented)
    missing = sorted(doc - impl)
    extra = sorted(impl - doc)
    return {
        "documented": sorted(doc),
        "implemented": sorted(impl),
        "documented_not_implemented": missing,
        "implemented_not_documented": extra,
        "documented_not_implemented_count": len(missing),
        "implemented_not_documented_count": len(extra),
    }


def resolve_paths(paths: Iterable[str], root: Path) -> dict:
    documented = sorted(set(paths))
    missing = [p for p in documented if not (root / p).exists()]
    present = [p for p in documented if (root / p).exists()]
    return {
        "documented": documented,
        "resolved": present,
        "documented_not_tree": missing,
        "documented_not_tree_count": len(missing),
        "resolved_count": len(present),
    }


def tree_files(root: Path, extra_skip: Iterable[str] = ()) -> set[str]:
    skip = {"docs.md", "parser.py", "schema.json", *extra_skip}
    out: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        rel = path.relative_to(root).as_posix()
        if path.name in skip or rel in skip:
            continue
        out.add(rel)
    return out
