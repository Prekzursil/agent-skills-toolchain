"""``python -m mkt`` entry point.

Delegates to :func:`mkt.cli.main`, which returns a real exit code. A ``python -m`` gate with no
executing ``main()`` is a permanently green no-op -- that hazard is why this file exists at all.
"""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
