"""``python -m wfmon_export`` entry point.

Dispatches to :func:`wfmon_export.cli.main`, which strips a single leading
``export`` token so ``python -m wfmon_export export <id>`` and
``python -m wfmon_export <id>`` both parse.
"""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
