"""``tools.cmdline_guard``: the Windows CreateProcess command-line guard.

The implementation lives in ``tools/command-center/cmdline_guard.py``; that
directory name is not importable as a package (hyphen), so the module is loaded
by file path once and its public names are re-exported here explicitly.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_REAL = Path(__file__).resolve().parent / "command-center" / "cmdline_guard.py"


def _load_real() -> ModuleType:
    cached = sys.modules.get("cmdline_guard")
    if cached is not None and getattr(cached, "__file__", None) == str(_REAL):
        return cached
    spec = importlib.util.spec_from_file_location("cmdline_guard", _REAL)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load cmdline_guard from {_REAL}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve `cls.__module__` through sys.modules during class
    # creation, so the module must be registered before it executes.
    sys.modules["cmdline_guard"] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop("cmdline_guard", None)
        raise
    return module


_real = _load_real()

E2BIG = _real.E2BIG
INLINE_PAYLOAD_THAT_DIED = _real.INLINE_PAYLOAD_THAT_DIED
Marshal = _real.Marshal
PROMPT_FILE_NAME = _real.PROMPT_FILE_NAME
SWITCH_EVENT = _real.SWITCH_EVENT
SpawnResult = _real.SpawnResult
TRANSPORT_FILE = _real.TRANSPORT_FILE
TRANSPORT_INLINE = _real.TRANSPORT_INLINE
WINDOWS_CREATEPROCESS_CHAR_CEILING = _real.WINDOWS_CREATEPROCESS_CHAR_CEILING
WINERROR_FILENAME_EXCED_RANGE = _real.WINERROR_FILENAME_EXCED_RANGE
emulated_206 = _real.emulated_206
format_switch_line = _real.format_switch_line
inline_argv = _real.inline_argv
marshal_prompt = _real.marshal_prompt
naive_linux_spawn = _real.naive_linux_spawn
pad_payload_for_inline_chars = _real.pad_payload_for_inline_chars
parse_child_report = _real.parse_child_report
payload_digest = _real.payload_digest
spawn_guarded = _real.spawn_guarded
switch_event = _real.switch_event
windows_cmdline_chars = _real.windows_cmdline_chars
would_raise_206 = _real.would_raise_206

__all__ = list(_real.__all__)
