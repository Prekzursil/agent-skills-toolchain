"""Import seam + the HERMETIC HOME binding for the routing lane.

PART 1 -- `sys.path`
--------------------
``platform`` is prepended to ``sys.path`` so this package resolves by its own name,
exactly as ``platform/lib/wfdsl/conftest.py`` does for ``wfdsl``. There is deliberately
NO ``platform/__init__.py``: the stdlib ``platform`` module always outranks a namespace
package, so creating one would shadow the standard library rather than expose this tree.
Probed on this box -- with the repo ROOT on ``sys.path``, ``import platform`` still
resolves to the stdlib, which is why the package is addressed as ``routing`` and never
as ``platform.routing``.

PART 2 -- the HOME binding (the hermeticity fix)
------------------------------------------------
`index.py:55` binds ``HOME = Path(os.environ.get("ROUTING_HOME") or Path.home())`` and
`Roots.live()` (`index.py:93-97`) hangs FIVE discovery roots off it: both skill vaults,
the plugin registry, ``.mcp.json``, the agent tree and the command tree. Nothing set
``ROUTING_HOME`` -- not a test, not CI -- so the lane silently measured whatever harness
the host happened to have installed.

MEASURED, two independent signals:

  * Linux runner, empty ``~/.claude`` -> ``discover()`` returned 383 records and 22 of
    this directory's tests failed, including the lane's own positive-form floor guard
    ("corpus implausibly small (383)"). Evidence: ``command-center/P13-LINUX-SUITE.json``.
  * Reproduced on Windows with ``ROUTING_HOME`` pointed at an empty temp directory:
    the identical 22 failures.

This module binds ``ROUTING_HOME`` to the committed fixture under ``fixtures/home/``
BEFORE any test module imports ``routing.index``, so the lane runs the same 912-record
corpus on any host with no live harness present.

Two bindings, not one, because the import order is not fully under our control: the
environment variable covers a fresh import and any subprocess, and ``index.HOME`` is
rebound directly in case something already imported the module. ``Roots.live()`` looks
``HOME`` up as a module global at CALL time, so the rebind takes effect for every later
``discover()``.

ESCAPE HATCH -- ``ROUTING_FIXTURE=0`` leaves both bindings alone, so the lane can be
pointed at a real harness (``ROUTING_HOME=~``) or at an empty directory. That second case
is the both-states control: with the fixture the suite passes, without it the corpus
guard must FIRE. A suite that passed in both states would be measuring nothing.
"""

from __future__ import annotations

import atexit
import contextlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

BUILD_ROOT = Path(__file__).resolve().parents[1]
if str(BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ROOT))

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE_HOME = FIXTURES / "home"

#: Set to "0"/"off"/"false" to leave `ROUTING_HOME` exactly as the caller left it.
_DISABLED = os.environ.get("ROUTING_FIXTURE", "").strip().lower() in {
    "0",
    "off",
    "false",
    "no",
}


def _bind_fixture_home() -> str | None:
    """Render the committed fixture to a session directory and bind it as HOME.

    The render exists for ONE field. `index.plugins()` follows each entry's
    ``installPath`` to a vendor manifest, and an absolute path cannot be committed --
    baking this machine's path into the repo is the exact host-coupling this fixture
    removes. So the committed registry carries a ``__FIXTURE_HOME__`` token and
    ``build_fixture.render()`` resolves it against wherever the tree is materialised.
    The same function is what the generator verified against, so the tests and the
    generator grade byte-identical trees.
    """
    if _DISABLED or not FIXTURE_HOME.is_dir():
        return None

    # Scoped path insert: prepending the fixtures directory for the whole session would
    # let any file dropped in there shadow a stdlib module by name. Take it back out as
    # soon as the import is done.
    sys.path.insert(0, str(FIXTURES))
    try:
        import build_fixture  # noqa: PLC0415 -- must not import before the path insert
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(str(FIXTURES))

    tmp = tempfile.mkdtemp(prefix="routing-fixture-home-")
    atexit.register(shutil.rmtree, tmp, True)
    home = build_fixture.render(FIXTURE_HOME, Path(tmp) / "home")

    os.environ["ROUTING_HOME"] = str(home)
    # Published so `test_fixture_hermetic.py` can tell "bound to the fixture" from
    # "deliberately pointed elsewhere" without importing this conftest (the routing
    # directory itself is not on `sys.path` -- only its parent is).
    os.environ["ROUTING_FIXTURE_ACTIVE"] = "1"
    # Belt and braces: rebind the already-computed module global too, in case some other
    # collected module imported `routing.index` before this conftest ran. Reading the env
    # var alone would be an import-order bet.
    from routing import index as _ix  # noqa: PLC0415

    _ix.HOME = home
    return str(home)


ROUTING_HOME = _bind_fixture_home()


def pytest_report_header(config) -> str:
    """State the corpus binding in the header, so a run can never be read out of context.

    A hermetic pass and a live-tree pass are different measurements and must not look
    identical in the log.
    """
    del config
    if ROUTING_HOME is None:
        return (
            "routing corpus: LIVE/EXTERNAL "
            f"(ROUTING_FIXTURE disabled={_DISABLED}, "
            f"ROUTING_HOME={os.environ.get('ROUTING_HOME') or Path.home()})"
        )
    return f"routing corpus: HERMETIC FIXTURE -> {ROUTING_HOME}"
