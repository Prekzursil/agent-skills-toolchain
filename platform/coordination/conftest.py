"""Make ``import coordination`` and ``import completion_predicate`` resolve under pytest.

Mirrors ``platform/lib/wfdsl/conftest.py``: ``platform/`` goes on ``sys.path`` so the
``coordination`` package resolves by its own name, and ``platform/lib`` goes on too so the SHARED
completion reducer resolves by ITS own name.

We deliberately do NOT put the repo ROOT on ``sys.path`` and there is deliberately no
``platform/__init__.py`` - that would turn the build root into a real package named ``platform``
and shadow the standard library module. Probed on this box: with the repo root on ``sys.path``,
``import platform`` still resolves to ``C:/Python314/Lib/platform.py``, so the shadowing risk is
real rather than theoretical.

Adding ``platform/`` itself (rather than the repo root) is safe: it makes ``coordination``
importable without introducing any module named ``platform``.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Callable

import pytest

HERE = Path(__file__).resolve().parent
PLATFORM_ROOT = HERE.parent
LIB_ROOT = PLATFORM_ROOT / "lib"

for entry in (str(PLATFORM_ROOT), str(LIB_ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from coordination.simclock import SimClock  # noqa: E402  - after the sys.path fix above
from coordination.store import Store  # noqa: E402


@pytest.fixture
def clock() -> SimClock:
    """A deterministic clock. Advance it explicitly; it never moves on its own."""
    return SimClock()


@pytest.fixture
def store(tmp_path: Path, clock: SimClock) -> Store:
    """An initialised coordination store under the test's own tmp_path.

    ``tmp_path`` matters: roughly twenty agents share one working tree in this program, so a test
    that wrote a coordination store into the repo would collide with a sibling and, worse, could
    leave records behind that a later run reads as real sessions.
    """
    return Store(root=tmp_path / "coord", clock=clock).initialise()


@pytest.fixture
def real_clock() -> Callable[[], float]:
    """Only for tests that genuinely need wall time (the cross-process lock probe)."""
    return time.time
