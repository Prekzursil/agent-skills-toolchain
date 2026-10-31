"""Lint banning `git archive` as a blob source (TST-0031).

    python -B archive_lint.py FILE [FILE...]
Exit 1 when any scanned file uses git archive to obtain file bytes; exit 0
when clean. `git archive` for release tarballs is fine; feeding it into a
formatter/hasher as if it were the blob is the defect this lint names.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BLOB_USE = re.compile(r"git\s+archive\b[^\n|]*\|\s*tar\b", re.IGNORECASE)


def lint_file(p: Path) -> list[str]:
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return [f"{p.as_posix()}:{i + 1}: git archive piped to tar as a blob source (use git cat-file -p)"
            for i, line in enumerate(text.splitlines()) if BLOB_USE.search(line)]


def main(argv: list[str]) -> int:
    hits: list[str] = []
    scanned = 0
    for a in argv:
        p = Path(a)
        if p.is_dir():
            for f in sorted(p.rglob("*.py")) + sorted(p.rglob("*.sh")) + sorted(p.rglob("*.md")):
                hits.extend(lint_file(f))
                scanned += 1
        elif p.is_file():
            hits.extend(lint_file(p))
            scanned += 1
    for h in hits:
        print(h)
    print(f"archive-lint: scanned={scanned} violations={len(hits)}")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
