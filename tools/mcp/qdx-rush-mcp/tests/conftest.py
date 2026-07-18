"""Test configuration for the flat qdx-rush MCP project.

The server module (``qdx_mcp_server.py``) imports the heavy optional runtime deps
``rush`` (rush-py) and ``mcp`` at import time.  ``rush-py`` 7.1.0 ships a Rust/PyO3
extension that only builds on CPython 3.12 (see ``pyproject.toml``), so it cannot be
imported on the interpreter these unit tests run under.  These tests target the pure
Python charge/energy *parsers*, which never touch the network or a RUSH token, so we
inject a lightweight ``rush`` stand-in into ``sys.modules`` **before** importing the
server.  No live keys, no network, no PyO3 build required.

``mcp`` is replaced with a trivial ``FastMCP`` whose ``@tool()`` is an identity
decorator, so the decorated MCP tools stay plain callables for the tests and the suite
stays hermetic (independent of the installed ``mcp`` version).  If a real ``mcp`` is
already imported in the process we leave it untouched so a sibling suite is not clobbered.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class _Keywords:
    """Generic keyword-object stand-in (records kwargs for introspection)."""

    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


class _StubResultRef:
    """Placeholder result ref; tests monkeypatch ``from_raw_output`` per case."""

    @staticmethod
    def from_raw_output(raw: object) -> object:  # pragma: no cover - overridden in tests
        raise NotImplementedError(
            "qdx_mcp_server.<module>.ResultRef.from_raw_output must be monkeypatched in tests"
        )


class _StubOptimizationResultRef(_StubResultRef):
    pass


def _install_rush_stub() -> None:
    if "rush" in sys.modules:
        return

    rush_mod = types.ModuleType("rush")

    class _RunError(Exception):
        pass

    rush_mod.RunError = _RunError
    rush_mod.RunSpec = _Keywords
    rush_mod.RunOpts = _Keywords

    # Lifecycle callables referenced only inside tool bodies (never called by these
    # parser unit tests) — present so the module imports cleanly.
    for _name in (
        "save_structure",
        "load_structure",
        "to_dict",
        "fetch_run_info",
        "collect_run",
        "fetch_runs",
        "delete_run",
    ):
        setattr(rush_mod, _name, lambda *a, **k: None)

    submodules = (
        "exess",
        "auto3d",
        "prepare",
        "boltz",
        "mmseqs2",
        "pbsa",
        "fried",
        "nnxtb",
    )
    for sub in submodules:
        mod = types.ModuleType(f"rush.{sub}")
        sys.modules[f"rush.{sub}"] = mod
        setattr(rush_mod, sub, mod)

    exess = sys.modules["rush.exess"]
    exess.ResultRef = _StubResultRef
    exess.OptimizationResultRef = _StubOptimizationResultRef
    for _kw in (
        "KSDFTKeywords",
        "ExportKeywords",
        "FragKeywords",
        "System",
        "Trajectory",
        "Restraints",
    ):
        setattr(exess, _kw, _Keywords)

    sys.modules["rush"] = rush_mod


def _install_mcp_stub() -> None:
    # Leave an already-imported real ``mcp`` untouched (avoids clobbering a sibling
    # suite); otherwise install an identity-decorator stub for a hermetic run.
    if "mcp" in sys.modules:
        return

    mcp_mod = types.ModuleType("mcp")
    server_mod = types.ModuleType("mcp.server")
    fastmcp_mod = types.ModuleType("mcp.server.fastmcp")

    class _FastMCP:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def tool(self, *dargs: object, **dkwargs: object):
            def _decorator(fn):
                return fn

            return _decorator

        def run(self, *args: object, **kwargs: object) -> None:
            pass

    fastmcp_mod.FastMCP = _FastMCP
    server_mod.fastmcp = fastmcp_mod
    mcp_mod.server = server_mod
    sys.modules["mcp"] = mcp_mod
    sys.modules["mcp.server"] = server_mod
    sys.modules["mcp.server.fastmcp"] = fastmcp_mod


_install_rush_stub()
_install_mcp_stub()
