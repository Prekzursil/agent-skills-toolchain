"""Argv-array invocation surface — re-exports the real lib.codex_invocation.

The implementation lives at repo-root ``lib/codex_invocation.py``; this module
keeps ``tools.lib``/``tools/lib`` importers on the same real code path instead
of a divergent copy.
"""
from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _Path

_IMPL = _Path(__file__).resolve().parents[2] / "lib" / "codex_invocation.py"
_spec = _ilu.spec_from_file_location("_codex_invocation_impl", _IMPL)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load {_IMPL}")
_mod = _ilu.module_from_spec(_spec)
_sys.modules.setdefault("_codex_invocation_impl", _mod)
_spec.loader.exec_module(_mod)

ECHO_SCRIPT = _mod.ECHO_SCRIPT
argv_bytes_match = _mod.argv_bytes_match
echo_child_argv = _mod.echo_child_argv
expected_hex = _mod.expected_hex

__all__ = ["ECHO_SCRIPT", "argv_bytes_match", "echo_child_argv", "expected_hex"]
