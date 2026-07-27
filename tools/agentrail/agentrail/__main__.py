"""``python -m agentrail`` -- the entry point the deployed ``agentrail.cmd`` shim calls.

Kept to two statements on purpose: everything worth testing lives in :func:`agentrail.cli.main`,
which returns an exit code instead of calling :func:`sys.exit`, so the whole command surface is
drivable from a test without catching :class:`SystemExit`.

There is NO ``# pragma: no cover`` on the guard below, and the usual excuse for one does not
apply. ``tests/test_main_module.py`` covers the FALSE arm by importing this module normally and
the TRUE arm with :func:`runpy.run_path`, which re-executes this file IN-PROCESS with
``__name__ == "__main__"``. Both arms are measured, and no subprocess is spawned -- so the
hermeticity rule and the zero-pragma rule are both kept, rather than one being traded for the
other.
"""

from __future__ import annotations

import sys

from agentrail.cli import main

if __name__ == "__main__":
    sys.exit(main())
