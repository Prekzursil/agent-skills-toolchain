#!/usr/bin/env python3
"""Structurally-unreadable census walker for BLD-0003.

Never calls os.path.relpath. A Phase-0 enumerator crashed with
`ValueError: path is on mount '\\\\.\\NUL'` because relpath cannot handle a
file literally named NUL. A swallowed crash would report every count as 0.
"""
from __future__ import annotations

import fnmatch
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

# Text-pipeline single-shot cap used by this census. Files larger than this
# remain pageable by offset, but a whole-file UTF-8 load is refused.
READ_CAP_BYTES = 1_048_576

GITCRYPT_MAGIC = b"\x00GITCRYPT\x00"
AGE_MAGIC = b"age-encryption.org/v1"
GITCRYPT_MAGIC = GITCRYPT_MAGIC
READ_CAP_BYTES = READ_CAP_BYTES
# emit.py / fixture.py aliases
READ_CAP_BYTES = READ_CAP_BYTES
GITCRYPT_MAGIC = GITCRYPT_MAGIC

WIN_RESERVED = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *{f"COM{i}" for i in range(1, 10)},
        *{f"LPT{i}" for i in range(1, 10)},
    }
)

CLASSES = (
    "BINARY",
    "ENCRYPTED",
    "OVERSIZED",
    "WIN_RESERVED",
    "LONG_PATH",
    "GITIGNORED",
)

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".ruff_cache",
        ".pytest_cache",
        "__pycache__",
        "node_modules",
    }
)


def safe_relpath(path: Path | str, root: Path | str) -> str:
    """Relative path without os.path.relpath (NUL-safe)."""
    p = os.path.abspath(os.fspath(path))
    r = os.path.abspath(os.fspath(root))
    if p == r:
        return "."
    prefix = r if r.endswith(os.sep) else r + os.sep
    if p.startswith(prefix):
        return p[len(prefix) :].replace("\\", "/")
    return os.path.basename(p)


def _component_reserved(name: str) -> bool:
    if not name:
        return False
    upper = name.upper()
    if upper in WIN_RESERVED:
        return True
    stem = upper.split(".", 1)[0]
    return stem in WIN_RESERVED


def path_is_win_reserved(rel: str) -> bool:
    for part in rel.replace("\\", "/").split("/"):
        if _component_reserved(part):
            return True
    return False


def is_encrypted(head: bytes) -> bool:
    return head.startswith(GITCRYPT_MAGIC) or head.startswith(AGE_MAGIC)


def is_utf8_text(head: bytes, size: int) -> bool:
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
        return True
    except UnicodeDecodeError as exc:
        if size > len(head) and exc.reason == "unexpected end of data":
            try:
                head[: exc.start].decode("utf-8")
                return True
            except UnicodeDecodeError:
                return False
        return False


def _read_head(path: Path, n: int = 8192) -> bytes:
    with open(path, "rb") as fh:
        return fh.read(n)


def load_gitignore_rules(root: Path) -> list[tuple[str, list[str]]]:
    rules: list[tuple[str, list[str]]] = []
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return rules
    patterns: list[str] = []
    try:
        text = gitignore.read_text(encoding="utf-8")
    except OSError:
        return rules
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    if patterns:
        rules.append(("", patterns))
    return rules


def gitignore_hit(rel: str, rules: list[tuple[str, list[str]]]) -> bool:
    rel = rel.replace("\\", "/")
    name = rel.rsplit("/", 1)[-1]
    for _base, patterns in rules:
        for pat in patterns:
            directory_only = pat.endswith("/")
            p = pat.rstrip("/")
            if directory_only:
                continue
            if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(name, p):
                return True
            if "/" not in p and fnmatch.fnmatch(name, p):
                return True
    return False


def classify_file(
    *,
    rel: str,
    size: int,
    head: bytes,
    ignored: bool,
    abs_len: int,
) -> list[str]:
    tags: list[str] = []
    if path_is_win_reserved(rel):
        tags.append("WIN_RESERVED")
    if len(rel) > 260 or abs_len > 260:
        tags.append("LONG_PATH")
    if ignored:
        tags.append("GITIGNORED")
    if size > READ_CAP_BYTES:
        tags.append("OVERSIZED")
    if is_encrypted(head):
        tags.append("ENCRYPTED")
    elif not is_utf8_text(head, size):
        tags.append("BINARY")
    return tags


def iter_files(root: Path) -> Iterable[Path]:
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except OSError:
            continue
        for ent in entries:
            try:
                if ent.is_symlink():
                    continue
                if ent.is_dir(follow_symlinks=False):
                    if ent.name in SKIP_DIR_NAMES:
                        continue
                    stack.append(Path(ent.path))
                elif ent.is_file(follow_symlinks=False):
                    yield Path(ent.path)
            except OSError:
                continue


def census(
    root: Path,
    *,
    skip_rel_prefixes: tuple[str, ...] = (),
    crash_inject: bool = False,
) -> dict[str, Any]:
    """Walk root and classify. Exceptions propagate; never return zero-on-crash."""
    root = Path(root)
    if crash_inject:
        raise ValueError("path is on mount '\\\\.\\NUL'")
    rules = load_gitignore_rules(root)
    by_class: dict[str, list[dict[str, Any]]] = {c: [] for c in CLASSES}
    files_seen = 0
    for path in iter_files(root):
        rel = safe_relpath(path, root)
        if any(rel.replace("\\", "/").startswith(p) for p in skip_rel_prefixes):
            continue
        files_seen += 1
        try:
            size = path.stat().st_size
            head = _read_head(path)
        except OSError:
            size = -1
            head = b""
        ignored = gitignore_hit(rel, rules)
        abs_len = len(os.path.abspath(os.fspath(path)))
        tags = classify_file(
            rel=rel,
            size=max(size, 0),
            head=head,
            ignored=ignored,
            abs_len=abs_len,
        )
        rec = {"path": rel, "path": rel, "bytes": size, "classes": tags}
        for tag in tags:
            by_class[tag].append(rec)
    counts = {c: len(by_class[c]) for c in CLASSES}
    return {
        "root": str(root),
        "files_seen": files_seen,
        "files_seen": files_seen,
        "counts": counts,
        "by_class": by_class,
        "read_cap_bytes": READ_CAP_BYTES,
        "relpath_impl": "string-prefix; never os.path.relpath",
        "relpath_impl": "string-prefix; never os.path.relpath",
        "completed_without_exception": True,
        "completed_without_exception": True,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: enumerator.py <root>", file=sys.stderr)
        return 2
    doc = census(Path(sys.argv[1]))
    slim = {
        "files_seen": doc["files_seen"],
        "counts": doc["counts"],
        "completed_without_exception": True,
        "read_cap_bytes": READ_CAP_BYTES,
    }
    print(json.dumps(slim, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
