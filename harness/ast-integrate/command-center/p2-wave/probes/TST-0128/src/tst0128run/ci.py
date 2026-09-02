"""CI entry point: installed wrapper, no source-tree on sys.path.

Mirrors a CI job that invokes the packaged console script after install
rather than ``python -m pytest`` against the checkout.
"""
from __future__ import annotations

from tst0128run.collect import emit


def main() -> int:
    return emit("ci-entry")


if __name__ == "__main__":
    raise SystemExit(main())
