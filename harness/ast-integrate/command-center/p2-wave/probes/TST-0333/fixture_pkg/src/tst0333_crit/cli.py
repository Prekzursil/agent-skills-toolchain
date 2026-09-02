"""Console-script entry: tst0333-crit."""

from __future__ import annotations

import sys

from .runner import run_suite


def main(argv: list[str] | None = None) -> int:
    return run_suite(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
