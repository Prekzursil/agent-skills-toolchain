"""Plugin-manifest command entry. Loads the dynamic config module on purpose."""
from __future__ import annotations

from pkg import helper, loader


def main() -> str:
    helper.used()
    loader.load()
    return "plugin-ok"


def unused_public() -> str:
    return "never-called-from-an-entry"


if __name__ == "__main__":
    print(main())
