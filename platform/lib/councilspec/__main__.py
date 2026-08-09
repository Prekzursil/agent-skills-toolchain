"""`python -m councilspec ...` entry point (avoids the runpy double-import warning)."""

from .validate import main

if __name__ == "__main__":
    raise SystemExit(main())
