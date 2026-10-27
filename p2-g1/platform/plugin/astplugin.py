"""Repo-side launcher: ``python platform/plugin/astplugin.py <verb> ...``.

The package uses relative imports, so running ``cli.py`` directly fails with
``attempted relative import with no known parent package``. This launcher puts ``platform/`` on
``sys.path`` and imports ``plugin.cli`` as a package, which is the same shape the shipped
``bin/astplugin.py`` uses against ``lib/``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plugin.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
