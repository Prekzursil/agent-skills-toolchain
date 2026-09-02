"""B08-shaped conformance subset: 3.10-syntax, no 3.11+ features."""
from __future__ import annotations


def add(left: int, right: int) -> int:
    return left + right


def main() -> int:
    if add(2, 3) != 5:
        print("FAILED:good_subset arithmetic")
        return 1
    print("GOOD_SUBSET_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
