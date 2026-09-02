#!/usr/bin/env python3
"""Fire iff a component's inline.sh has an interior apostrophe that splits a
single-quoted python -c payload. Exit 2 = fired, 0 = silent."""
from __future__ import annotations

import sys
from pathlib import Path


def apostrophe_splits_single_quoted_payload(text: str) -> bool:
    i = 0
    while i < len(text):
        if text[i] == "'":
            j = text.find("'", i + 1)
            if j < 0:
                return True
            inner = text[i + 1 : j]
            rest = text[j + 1 :]
            if inner.endswith("(") and rest[:1].isalpha():
                return True
            i = j + 1
        else:
            i += 1
    return False


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: repro_unquoted_apostrophe.py <component-dir>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    snippet = root / "inline.sh"
    if not snippet.is_file():
        print(f"missing {snippet}", file=sys.stderr)
        return 2
    text = snippet.read_text(encoding="utf-8")
    if apostrophe_splits_single_quoted_payload(text):
        print("FIRE unquoted-apostrophe")
        return 2
    print("silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
