"""Installed console script entry (pytest analogue)."""
from __future__ import annotations

from tst0128run.collect import emit


def main() -> int:
    return emit("console-script")


if __name__ == "__main__":
    raise SystemExit(main())
