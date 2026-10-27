#!/usr/bin/env python3
"""Build ast_examples wheel. Omits the source-tree-only marker module."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src" / "ast_examples"
NAME = "ast_examples"
VER = "0.0.1"
SKIP = {"_source_tree_only.py"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dest_dir = Path(argv[0] if argv else "dist")
    dest_dir.mkdir(parents=True, exist_ok=True)
    wheel = dest_dir / f"{NAME}-{VER}-py3-none-any.whl"
    if not SRC.is_dir():
        print(f"missing package src {SRC}", file=sys.stderr)
        return 1
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(SRC.rglob("*")):
            if not path.is_file():
                continue
            if path.name in SKIP or path.suffix == ".pyc":
                continue
            arc = f"{NAME}/{path.relative_to(SRC).as_posix()}"
            zf.write(path, arcname=arc)
        zf.writestr(
            f"{NAME}-{VER}.dist-info/METADATA",
            (
                f"Metadata-Version: 2.1\nName: {NAME}\nVersion: {VER}\n"
                "Summary: Documented ast-integrate examples\n"
            ),
        )
        zf.writestr(
            f"{NAME}-{VER}.dist-info/WHEEL",
            "Wheel-Version: 1.0\nGenerator: ast-examples-build\n"
            "Root-Is-Purelib: true\nTag: py3-none-any\n",
        )
    print(str(wheel))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
