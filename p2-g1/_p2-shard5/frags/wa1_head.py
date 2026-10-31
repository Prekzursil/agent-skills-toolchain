"""Windows launch adapter: PATHEXT/.cmd resolve + argv spawn (IMP-0013).

Launch path is fenced so a source scan can prove it does not shell out to
Git-Bash. POSIX ``command -v`` is a second instrument, never the launch path.

2026-10-24 shard-5 fixes:
* write_cmd_shim now emits a real Windows batch shim. The previous content
  was a POSIX python script with a shebang; cmd.exe executed it line-by-line
  as batch text ("Unable to initialize device PRN") and the shim never
  launched.
* posix_command_v_live falls back to shutil.which("sh")/("bash") so the
  second instrument is LIVE on Windows dev hosts (Git Bash supplies sh)
  instead of a vacuous None because /bin/sh does not exist as a Windows
  drive path.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

PATHEXT_DEFAULT = ".COM;.EXE;.BAT;.CMD;.VBS;.JS;.WS;.MSC"


class LaunchAdapterError(Exception):
    def __init__(self, code: str, message: str, **ctx: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.ctx = ctx


@dataclass
class Resolution:
    used_for_launch: str
    get_command_path: str | None
    posix_command_v: str | None
    disagreement: bool
    disagreement_kind: str | None

    def as_json(self) -> dict:
        return {
            "used_for_launch": self.used_for_launch,
            "get_command_path": self.get_command_path,
            "posix_command_v": self.posix_command_v,
            "disagreement": self.disagreement,
            "disagreement_kind": self.disagreement_kind,
        }
