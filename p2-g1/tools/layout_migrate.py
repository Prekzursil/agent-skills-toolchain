#!/usr/bin/env python3
"""layout_migrate -- the documented TST-0256 migration (docs/layout-migration.md).

Mapping (verbatim from the guide's table):
    src/      -> tools/
    cc/       -> command-center/
    handbook/ -> docs/

Conversion is LF-normalized and path-separator independent. Files outside the
mapped prefixes are never touched. ``--apply`` is idempotent by construction:
on an already-migrated tree it moves nothing (noop).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

MAPPING: list[tuple[str, str]] = [
    ("src", "tools"),
    ("cc", "command-center"),
    ("handbook", "docs"),
]


def normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def target_for(rel: Path) -> Path | None:
    """New path for a mapped old-prefix file, else None (unmapped = untouched)."""
    parts = rel.parts
    if not parts:
        return None
    head = parts[0].lower()
    for old, new in MAPPING:
        if head == old:
            return Path(new, *parts[1:])
    return None


def apply_tree(tree: Path) -> dict:
    moved: list[dict] = []
    skipped_missing: list[str] = []
    for p in sorted(tree.rglob("*")):
        if not p.is_file() or ".git" in p.parts:
            continue
        rel = p.relative_to(tree)
        tgt = target_for(rel)
        if tgt is None:
            continue
        if not p.is_file():
            skipped_missing.append(rel.as_posix())
            continue
        tgt_abs = tree / tgt
        tgt_abs.parent.mkdir(parents=True, exist_ok=True)
        data = normalize(p.read_bytes())
        tgt_abs.write_bytes(data)
        p.unlink()
        moved.append({"from": rel.as_posix(), "to": tgt.as_posix()})
    # Prune now-empty mapped source dirs so the old layout is fully vacated.
    for old, _new in MAPPING:
        d = tree / old
        if d.is_dir():
            for sub in sorted((q for q in d.rglob("*") if q.is_dir()), reverse=True):
                try:
                    sub.rmdir()
                except OSError:
                    pass
            try:
                d.rmdir()
            except OSError:
                pass
    return {"action": "migrated" if moved else "noop", "moved": moved}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Apply the documented layout migration.")
    ap.add_argument("--apply", action="store_true", help="apply the mapping in place")
    ap.add_argument("--tree", default=".", help="tree root (default: cwd)")
    args = ap.parse_args(argv)
    if not args.apply:
        print("FAILED:layout_migrate nothing to do (pass --apply)")
        return 2
    tree = Path(args.tree).resolve()
    if not tree.is_dir():
        print(f"FAILED:layout_migrate tree-absent {tree}")
        return 2
    result = apply_tree(tree)
    print(
        f"SUCCESS:layout_migrate action={result['action']} moved={len(result['moved'])}"
    )
    for m in result["moved"]:
        print(f"  {m['from']} -> {m['to']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
