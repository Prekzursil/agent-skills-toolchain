"""Registry of the additional in-process lane modules (gem-hunt program, waves 2-4).

Why a registry and not more code in ``adapters.py``: that file already carries the
adapter base, TrailSearch, OSSInsight, GitHub REST and ``read_url``. Every further lane
lives in its own module (``lane_<name>.py``) exposing one function::

    def build(environ) -> list[SelfHostedAdapter]

The lane decides its own flag semantics (a default-ON keyless lane uses a kill
switch, a keyed or heavy lane is opt-in), reads secrets by env NAME only, and must
be import-safe with no network and no third-party dependency at import time.

``extra_adapters`` wires every registered lane. It fails CLOSED per lane, never
per hub: an import error or a builder exception drops that lane and records a
truthful reason under ``lane:<module>`` in the degraded map the hub already
prints (``hub.py --print-plan``), instead of taking the whole server down or
silently pretending the lane is there.
"""

from __future__ import annotations

import importlib
from typing import Any

#: Lane modules the hub wires, in listing order. Append a module here only once it
#: exists on the branch and its own tests are green; a name listed here that does
#: not import is reported as degraded, on purpose.
LANE_MODULES: tuple[str, ...] = (
    "lane_repo_health",  # bestofjs v2 + deps.dev + OpenSSF Scorecard (keyless, default ON)
    "lane_wiki",  # Wikipedia + Wayback + Hacker News grounding (keyless, default ON)
)


def build_lane(module_name: str, environ) -> list[Any]:
    """Import ``module_name`` and return its ``build(environ)`` list.

    Raises whatever the import or the builder raises; ``extra_adapters`` is the
    fail-closed wrapper. Kept separate so a lane's own tests can wire it without
    being registered yet.
    """
    module = importlib.import_module(module_name)
    build = getattr(module, "build", None)
    if not callable(build):
        raise TypeError(f"lane module {module_name!r} has no callable build(environ)")
    built = build(environ)
    if not isinstance(built, list):
        raise TypeError(
            f"lane module {module_name!r}.build must return a list, got "
            f"{type(built).__name__}"
        )
    return built


def extra_adapters(
    environ, modules: tuple[str, ...] | None = None
) -> tuple[list[Any], dict[str, str]]:
    """Build every registered lane; return ``(adapters, degraded)``.

    ``degraded`` maps ``"lane:<module>"`` to a one-line reason for each lane that
    could not be wired. A lane that builds to an empty list (its flag is off) is
    neither wired nor degraded -- that is the lane saying "not now", truthfully.
    """
    built: list[Any] = []
    degraded: dict[str, str] = {}
    for name in LANE_MODULES if modules is None else modules:
        try:
            built.extend(build_lane(name, environ))
        except Exception as exc:  # noqa: BLE001 - fail closed per lane, report why
            degraded[f"lane:{name}"] = f"{type(exc).__name__}: {exc}"
    return built, degraded
