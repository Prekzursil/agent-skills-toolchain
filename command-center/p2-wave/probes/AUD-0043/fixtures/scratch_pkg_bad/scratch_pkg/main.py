"""Console-script entry point that imports the SECOND top-level package.

If helper_mod is dropped from [tool.setuptools] packages in a scratch build, the
wheel ships scratch_pkg without helper_mod and this import raises ModuleNotFoundError
ONLY in the installed run -- a plain ``python -m pytest`` against this source tree
never observes the omission because the file is still present on disk.
"""

from __future__ import annotations

from helper_mod.helper import compute


def main() -> int:
    result = compute(2, 3)
    print(f"scratch-cli: compute(2, 3)={result}")
    return 0 if result == 5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
