"""macOS launch adapter: zsh default shell, BSD flagsets, quarantine-aware spawn.

The adapter is a thin launcher around subprocess with three macOS-specific
concerns made explicit and testable on any POSIX host:

* host signals: two independent probes (a launched child's ``uname -s`` and
  ``sys.platform``) that must agree before any Darwin-only behaviour engages —
  the adapter never rewrites a non-Darwin host into Darwin;
* flagsets: BSD versus GNU userland flag differences (``sed -i ''`` versus
  ``sed -i``) selected from the measured host, never assumed;
* quarantine: launching a fixture carrying the ``com.apple.quarantine``
  attribute is refused until the attribute is cleared. On non-Darwin hosts a
  sidecar-file backend emulates the xattr so the both-states control stays
  executable on Linux CI.
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

# Named, stable error codes. Callers branch on these, never on message text.
EMPTY_ARGV = "EMPTY_ARGV"
MACOS_SUBSTRATE_MISSING = "MACOS_SUBSTRATE_MISSING"
QUARANTINE_BLOCKED = "QUARANTINE_BLOCKED"
TOOL_NOT_FOUND = "TOOL_NOT_FOUND"

_PLATFORM_TO_UNAME = {
    "darwin": "Darwin",
    "linux": "Linux",
    "win32": "Windows",
    "cygwin": "Windows",
}

_BSD_FLAGS = {
    "kind": "bsd",
    "sed_inplace": ["sed", "-i", ""],
    "stat_size": ["stat", "-f", "%z"],
    "xattr_delete": ["xattr", "-d", QUARANTINE_ATTR],
}
_GNU_FLAGS = {
    "kind": "gnu",
    "sed_inplace": ["sed", "-i"],
    "stat_size": ["stat", "-c", "%s"],
    "xattr_delete": ["setfattr", "-x", "user." + QUARANTINE_ATTR],
}


class AdapterError(RuntimeError):
    """Single-line, named-code launch refusal. Never a traceback."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Launched:
    returncode: int
    stdout: str
    stderr: str
    argv: list[str]
    uname_inside: str | None = None


def child_uname() -> str:
    """Signal 1: sysname reported by a genuinely launched child process."""
    exe = shutil.which("uname")
    if exe:
        proc = subprocess.run([exe, "-s"], capture_output=True, text=True)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    proc = subprocess.run(
        [sys.executable, "-c", "import os; print(os.uname().sysname)"],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def host_signals() -> dict:
    """Two independent host signals; darwin=True only when both say Darwin."""
    signal1 = child_uname()
    signal2 = sys.platform
    expected = _PLATFORM_TO_UNAME.get(signal2, signal2)
    agree = bool(signal1) and signal1 == expected
    return {
        "signal1_child_uname": signal1,
        "signal2_sys_platform": signal2,
        "signals_agree": agree,
        "darwin": agree and signal1 == "Darwin",
        "interpreter": sys.executable,
        "default_shell": DEFAULT_SHELL,
    }


def _copy_flagset(flags: dict) -> dict:
    return {k: (list(v) if isinstance(v, list) else v) for k, v in flags.items()}


def flagset(kind: str | None = None) -> dict:
    """BSD or GNU userland flags; kind=None selects from the measured host."""
    if kind is None:
        kind = "bsd" if host_signals()["darwin"] else "gnu"
    if kind == "bsd":
        return _copy_flagset(_BSD_FLAGS)
    if kind == "gnu":
        return _copy_flagset(_GNU_FLAGS)
    raise AdapterError(TOOL_NOT_FOUND, f"unknown flagset kind: {kind!r}")


def flags_differ() -> bool:
    return _BSD_FLAGS["sed_inplace"] != _GNU_FLAGS["sed_inplace"]


class SidecarXattrBackend:
    """Quarantine emulation: the xattr lives in a sidecar file next to the
    payload, so the both-states control is executable where real
    com.apple.quarantine xattrs do not exist."""

    name = "sidecar-xattr"

    def sidecar(self, path: Path | str) -> Path:
        p = Path(path)
        return p.with_name(p.name + ".quarantine-xattr")

    def set_quarantine(self, path: Path | str, value: str = "0083;imp0014;fixture") -> None:
        self.sidecar(path).write_text(
            f"{QUARANTINE_ATTR}={value}\n", encoding="utf-8"
        )

    def clear_quarantine(self, path: Path | str) -> None:
        sidecar = self.sidecar(path)
        if sidecar.exists():
            sidecar.unlink()

    def is_quarantined(self, path: Path | str) -> bool:
        return self.sidecar(path).exists()


class MacOSLaunchAdapter:
    """Spawns argv lists (never shell strings) with quarantine preflight."""

    def __init__(
        self,
        backend: SidecarXattrBackend,
        zsh_path: str | None = None,
        require_darwin: bool = False,
    ) -> None:
        self.backend = backend
        self._zsh_path = zsh_path
        self.require_darwin = require_darwin

    def zsh(self) -> Path:
        if self._zsh_path:
            return Path(self._zsh_path)
        found = shutil.which(DEFAULT_SHELL)
        return Path(found) if found else Path("/bin/zsh")

    def _preflight(self, argv: list[str]) -> None:
        if not argv:
            raise AdapterError(EMPTY_ARGV, "argv is empty; nothing to launch")
        if self.require_darwin and not host_signals()["darwin"]:
            raise AdapterError(
                MACOS_SUBSTRATE_MISSING,
                "require_darwin=True but this host's signals are not Darwin",
            )
        tool = str(argv[0])
        if not Path(tool).is_file() and shutil.which(tool) is None:
            raise AdapterError(TOOL_NOT_FOUND, f"launch tool not found: {tool}")
        for part in argv:
            candidate = Path(str(part))
            if candidate.is_file() and self.backend.is_quarantined(candidate):
                raise AdapterError(
                    QUARANTINE_BLOCKED,
                    f"{QUARANTINE_ATTR} present on {candidate.name}; clear it before launch",
                )

    def launch(self, argv: Sequence[str], capture_uname: bool = False) -> Launched:
        argv_list = [str(a) for a in argv]
        self._preflight(argv_list)
        proc = subprocess.run(argv_list, capture_output=True, text=True)
        uname_inside = child_uname() if capture_uname else None
        return Launched(
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            argv=argv_list,
            uname_inside=uname_inside,
        )

    def launch_shell_script(self, script: Path | str) -> Launched:
        return self.launch([str(self.zsh()), str(script)])


def quarantine_both_states(root: Path) -> dict:
    """Both-states control: quarantined fixture is refused, clears then runs,
    and an identical clean fixture is never blocked."""
    backend = SidecarXattrBackend()
    adapter = MacOSLaunchAdapter(backend=backend)

    quarantined = root / "quarantined_fixture.py"
    quarantined.write_text("print('LAUNCHED')\n", encoding="utf-8")
    backend.set_quarantine(quarantined)

    before: dict = {"raised": False, "code": None, "message": None}
    try:
        adapter.launch([sys.executable, str(quarantined)])
    except AdapterError as exc:
        before = {"raised": True, "code": exc.code, "message": str(exc)}

    backend.clear_quarantine(quarantined)
    run = adapter.launch([sys.executable, str(quarantined)])
    after = {
        "stdout": (run.stdout or "").strip(),
        "returncode": run.returncode,
        "quarantined_after_clear": backend.is_quarantined(quarantined),
    }

    clean = root / "clean_fixture.py"
    clean.write_text("print('CLEAN-OK')\n", encoding="utf-8")
    clean_run = adapter.launch([sys.executable, str(clean)])
    clean_not_blocked = clean_run.returncode == 0 and "CLEAN-OK" in clean_run.stdout

    ok = (
        before["raised"]
        and before["code"] == QUARANTINE_BLOCKED
        and after["returncode"] == 0
        and after["stdout"] == "LAUNCHED"
        and not after["quarantined_after_clear"]
        and clean_not_blocked
    )
    return {
        "pass": ok,
        "before": before,
        "after": after,
        "clean_not_blocked": clean_not_blocked,
        "backend": backend.name,
    }


def missing_tool_control() -> dict:
    """A missing tool must surface as a one-line named error, not a traceback."""
    adapter = MacOSLaunchAdapter(backend=SidecarXattrBackend())
    missing = os.path.join(os.sep, "nonexistent", "imp0014-no-such-tool")
    try:
        adapter.launch([missing, "--version"])
    except AdapterError as exc:
        message = str(exc)
        not_traceback = "Traceback" not in message and "\n" not in message.strip()
        return {
            "pass": exc.code == TOOL_NOT_FOUND,
            "code": exc.code,
            "not_traceback": not_traceback,
            "message": message,
        }
    return {
        "pass": False,
        "code": None,
        "not_traceback": False,
        "message": "launch of a nonexistent tool unexpectedly succeeded",
    }
