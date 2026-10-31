"""G-1 Windows shell shim (platform-only, no check logic).

The G-1 estate command strings are bash-syntax ("ENV=1 python3 -B ...").
On Windows, subprocess(shell=True) would route them to cmd.exe, which
cannot parse env-assignment prefixes. This shim routes shell=True string
commands through Git Bash instead. Probe selection, exit-code checking,
hashing, and every completion-predicate check are untouched.
"""
from __future__ import annotations

import os

if os.name == "nt":  # pragma: no cover - platform shim
    import subprocess as _sp

    _BASH_CANDIDATES = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\msys64\usr\bin\bash.exe",
    ]
    _BASH = next((p for p in _BASH_CANDIDATES if os.path.isfile(p)), None)

    if _BASH:
        _orig_popen_init = _sp.Popen.__init__

        def _popen_init(self, args, **kwargs):  # noqa: ANN001, ANN003
            try:
                if (
                    kwargs.get("shell")
                    and isinstance(args, str)
                    and os.name == "nt"
                ):
                    args = [_BASH, "-c", args]
                    kwargs["shell"] = False
            except Exception:
                pass
            return _orig_popen_init(self, args, **kwargs)

        _sp.Popen.__init__ = _popen_init
