"""python -m tst0128run  — source-tree / module invocation."""
from __future__ import annotations

from tst0128run.collect import emit


def main() -> int:
    return emit("python-m")


if __name__ == "__main__":
    raise SystemExit(main())
