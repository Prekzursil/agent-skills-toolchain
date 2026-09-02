#!/usr/bin/env python3
"""Naive-user next command for one failure-taxonomy class.

Exit 0 when the class is mapped. Exit 2 when it is unmapped (the control
that a class added later is reported rather than force-fitted).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import error_catalog as C  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Print the actionable error catalog row.")
    p.add_argument("--class", dest="taxonomy_class", required=True)
    args = p.parse_args(argv)
    cls = args.taxonomy_class.strip()
    text = C.render(cls)
    sys.stdout.write(text)
    if not C.is_actionable(C.CATALOG.get(cls)):
        sys.stdout.write("OK:unmapped\n")
        return 2
    sys.stdout.write("OK:mapped\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
