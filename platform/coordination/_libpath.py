"""Side-effect module: put ``platform/lib`` on ``sys.path``.

The SHARED completion reducer lives at ``platform/lib/completion_predicate.py`` and imports its
own siblings by bare name (``from vendor_identity import compare``). ``platform/`` deliberately
has NO ``__init__.py`` - ``platform/lib/wfdsl/conftest.py`` records why: making the build root a
real package named ``platform`` would shadow the standard library module of the same name, and it
was probed on this box that with the repo root on ``sys.path``, ``import platform`` still resolves
to ``C:/Python314/Lib/platform.py``.

So the reducer cannot be reached by a relative import from this package, and duplicating it is
forbidden. Prepending ``platform/lib`` is the same mechanism the three existing conftest files
already use; doing it here as well means the coordination modules also work outside pytest (probe
scripts, ``python -m``), not only under a conftest.

Import for the side effect only::

    from . import _libpath  # noqa: F401
"""

from __future__ import annotations

import sys
from pathlib import Path

LIB_ROOT = Path(__file__).resolve().parents[1] / "lib"

if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))
