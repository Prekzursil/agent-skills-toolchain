"""macOS launch adapter: zsh default shell, BSD flagsets, quarantine-aware spawn.

2026-10-24 shard-5 adaptation: host signals are compared as OS FAMILIES
(Windows/Darwin/Linux) with the raw child uname string preserved, and
launch() interposes a POSIX shell for shebang scripts on Windows hosts so
the both-states contract stays executable where native exec of a #! file
is impossible (WinError 193). Darwin detection stays exact: a Windows host
can never be fabricated into Darwin.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

DEFAULT_SHELL = "zsh"
QUARANTINE_ATTR = "com.apple.quarantine"

EMPTY_ARGV = "EMPTY_ARGV"
MACOS_SUBSTRATE_MISSING = "MACOS_SUBSTRATE_MISSING"
QUARANTINE_BLOCKED = "QUARANTINE_BLOCKED"
TOOL_NOT_FOUND = "TOOL_NOT_FOUND"

_PLATFORM_FAMILY = {
    "win32": "Windows",
    "cygwin": "Windows",
    "darwin": "Darwin",
    "linux": "Linux",
}

_UNAME_FAMILY_PREFIXES = (
    ("MINGW", "Windows"),
    ("MSYS", "Windows"),
    ("CYGWIN", "Windows"),
    ("Windows", "Windows"),
    ("Darwin", "Darwin"),
    ("Linux", "Linux"),
)


def uname_family(raw: str) -> str:
    for prefix, family in _UNAME_FAMILY_PREFIXES:
        if raw.startswith(prefix):
            return family
    return raw


class AdapterError(RuntimeError):
    """Single-line, named-code launch refusal. Never a traceback."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
