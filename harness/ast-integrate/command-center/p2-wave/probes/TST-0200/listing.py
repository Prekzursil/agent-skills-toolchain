#!/usr/bin/env python3
"""Independent recursive listing of an install destination.

Signal (b) for TST-0200: os.scandir walk, not the installer's planned table.
Classifies ABSENT / EMPTY / COMPLETE / PARTIAL. PARTIAL is the forbidden state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from installer import lf, normalize_rel, sha256_bytes  # noqa: E402


def walk_files(root: Path) -> list[dict[str, Any]]:
    """os.scandir recursion; skips the installer tmp suffix if any linger."""
    root = Path(root)
    out: list[dict[str, Any]] = []
    if not root.exists():
        return out

    def rec(cur: Path) -> None:
        try:
            with os.scandir(cur) as it:
                entries = list(it)
        except FileNotFoundError:
            return
        for ent in entries:
            name = ent.name
            if name.endswith(".tst0200-tmp"):
                continue
            path = Path(ent.path)
            if ent.is_dir(follow_symlinks=False):
                rec(path)
                continue
            if not ent.is_file(follow_symlinks=False):
                continue
            rel = path.relative_to(root).as_posix()
            data = path.read_bytes()
            out.append(
                {
                    "rel": rel,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(lf(data)).hexdigest(),
                }
            )

    rec(root)
    out.sort(key=lambda r: r["rel"])
    return out


def classify(dest: Path, package: dict[str, str]) -> dict[str, Any]:
    dest = Path(dest)
    expected = {
        normalize_rel(rel): sha256_bytes(body.encode("utf-8"))
        for rel, body in package.items()
    }
    if not dest.exists():
        return {
            "state": "ABSENT",
            "file_count": 0,
            "files": [],
            "expected_count": len(expected),
            "missing": sorted(expected),
            "extra": [],
            "mismatch": [],
            "complete": False,
            "partial": False,
            "empty_or_absent": True,
        }
    files = walk_files(dest)
    found = {r["rel"]: r["sha256"] for r in files}
    missing = sorted(set(expected) - set(found))
    extra = sorted(set(found) - set(expected))
    mismatch = sorted(
        rel for rel in set(expected) & set(found) if expected[rel] != found[rel]
    )
    complete = not missing and not extra and not mismatch
    empty = len(files) == 0
    partial = (not complete) and (not empty)
    if empty:
        state = "EMPTY"
    elif complete:
        state = "COMPLETE"
    else:
        state = "PARTIAL"
    return {
        "state": state,
        "file_count": len(files),
        "files": files,
        "expected_count": len(expected),
        "missing": missing,
        "extra": extra,
        "mismatch": mismatch,
        "complete": complete,
        "partial": partial,
        "empty_or_absent": empty,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TST-0200 independent listing")
    parser.add_argument("--dest", required=True)
    parser.add_argument("--package", required=True)
    args = parser.parse_args(argv)
    package = json.loads(Path(args.package).read_text(encoding="utf-8"))
    report = classify(Path(args.dest), {str(k): str(v) for k, v in package.items()})
    print(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
