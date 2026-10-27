"""Process layer: explicit interpreters, argv-array-only invocation, per-OS launch adapters.

Three rules, each of which has cost this estate real damage:

1. **Explicit interpreters (IMP-0012/0016).** A script entrypoint declares its interpreter id
   and version floor; nothing is ever run through an inferred one. ``bash`` on this box resolves
   to WSL's ``bash.exe``, which mangles Windows paths and rejects CRLF, so "just run the .sh"
   is not a portable instruction.
2. **argv arrays only (IMP-0019).** No command-string concatenation anywhere, so a space or an
   apostrophe in a path can never re-parse as shell syntax.
3. **Scoped path conversion (IMP-0020).** MSYS rewrites ``/c/...``-shaped *arguments*; disabling
   it globally then breaks the arguments that legitimately need conversion. The suppression is
   applied per-argument-list, never exported process-wide.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .errors import PluginError

#: OS ids used by the launch adapters. Keys are stable contract values.
OS_WINDOWS = "windows"
OS_MACOS = "macos"
OS_LINUX = "linux"


def current_os() -> str:
    if sys.platform == "win32":
        return OS_WINDOWS
    if sys.platform == "darwin":
        return OS_MACOS
    return OS_LINUX


@dataclass(frozen=True)
class Interpreter:
    """A declared interpreter: how to find it, how to ask its version, what floor it must meet."""

    ident: str
    #: Candidate executables, in preference order, per OS. ``"*"`` = any OS.
    candidates: dict[str, tuple[str, ...]]
    version_argv: tuple[str, ...]
    version_re: str
    floor: tuple[int, ...]
    #: argv prefix used to execute a script file with this interpreter.
    exec_prefix: tuple[str, ...] = ()

    def candidate_names(self, os_name: str) -> tuple[str, ...]:
        return self.candidates.get(os_name, self.candidates.get("*", ()))


INTERPRETERS: dict[str, Interpreter] = {
    "python3": Interpreter(
        ident="python3",
        candidates={
            OS_WINDOWS: ("python", "python3", "py"),
            "*": ("python3", "python"),
        },
        version_argv=("--version",),
        version_re=r"Python (\d+)\.(\d+)\.(\d+)",
        floor=(3, 10, 0),
    ),
    "node": Interpreter(
        ident="node",
        candidates={"*": ("node",)},
        version_argv=("--version",),
        version_re=r"v(\d+)\.(\d+)\.(\d+)",
        floor=(18, 0, 0),
    ),
    "pwsh": Interpreter(
        ident="pwsh",
        candidates={OS_WINDOWS: ("pwsh", "powershell"), "*": ("pwsh",)},
        version_argv=("-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"),
        version_re=r"(\d+)\.(\d+)\.(\d+)",
        floor=(7, 0, 0),
        exec_prefix=("-NoProfile", "-ExecutionPolicy", "Bypass", "-File"),
    ),
    "bash": Interpreter(
        ident="bash",
        # On Windows, system32\bash.exe is WSL: it rejects CRLF and mangles Windows paths.
        # Git Bash is named explicitly so the adapter never silently selects WSL.
        candidates={
            OS_WINDOWS: (r"C:\Program Files\Git\bin\bash.exe", "bash"),
            "*": ("bash",),
        },
        version_argv=("--version",),
        version_re=r"version (\d+)\.(\d+)\.(\d+)",
        floor=(4, 0, 0),
    ),
}


@dataclass
class InterpreterProbe:
    """The result of looking for one declared interpreter on this machine."""

    ident: str
    found: bool
    path: str | None = None
    version: tuple[int, ...] | None = None
    floor: tuple[int, ...] = ()
    meets_floor: bool = False
    detail: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "interpreter": self.ident,
            "found": self.found,
            "path": self.path,
            "version": ".".join(str(n) for n in self.version) if self.version else None,
            "floor": ".".join(str(n) for n in self.floor) if self.floor else None,
            "meets_floor": self.meets_floor,
            "detail": self.detail,
        }


def _parse_version(text: str, pattern: str) -> tuple[int, ...] | None:
    m = re.search(pattern, text)
    if not m:
        return None
    return tuple(int(g) for g in m.groups())


def probe_interpreter(ident: str, *, os_name: str | None = None) -> InterpreterProbe:
    """Locate a declared interpreter and check its version floor. Never guesses."""
    if ident not in INTERPRETERS:
        return InterpreterProbe(
            ident, False, floor=(), detail="interpreter id is not declared"
        )
    spec = INTERPRETERS[ident]
    osn = os_name or current_os()
    for name in spec.candidate_names(osn):
        path = (
            name if os.path.isabs(name) and Path(name).exists() else shutil.which(name)
        )
        if not path:
            continue
        try:
            cp = subprocess.run(  # noqa: S603 - argv array, shell=False, fixed argv
                [path, *spec.version_argv],
                capture_output=True,
                text=True,
                timeout=30,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return InterpreterProbe(
                ident, True, path, None, spec.floor, False, f"probe failed: {exc}"
            )
        version = _parse_version((cp.stdout or "") + (cp.stderr or ""), spec.version_re)
        if version is None:
            return InterpreterProbe(
                ident, True, path, None, spec.floor, False, "version unparseable"
            )
        ok = version >= spec.floor
        return InterpreterProbe(
            ident,
            True,
            path,
            version,
            spec.floor,
            ok,
            "ok" if ok else f"below floor {'.'.join(map(str, spec.floor))}",
        )
    return InterpreterProbe(
        ident, False, None, None, spec.floor, False, "not found on PATH"
    )


def require_interpreter(ident: str) -> InterpreterProbe:
    """Probe and fail loudly (``E_INTERP``). The only sanctioned pre-exec check."""
    p = probe_interpreter(ident)
    if not p.found:
        raise PluginError(
            "E_INTERP", f"interpreter {ident!r} not found", context=p.as_dict()
        )
    if not p.meets_floor:
        raise PluginError(
            "E_INTERP", f"interpreter {ident!r} {p.detail}", context=p.as_dict()
        )
    return p


#: Arguments that must keep their POSIX spelling (git revisions, pathspecs) — the ONLY place
#: MSYS path conversion is suppressed, and only for the duration of one call.
_REVISION_SHAPED = re.compile(r"^(?:[^\s:]+:[^\s:]+|HEAD[~^].*|refs/.*)$")


def _needs_pathconv_suppression(argv: list[str]) -> bool:
    return any(_REVISION_SHAPED.match(a) for a in argv[1:])


@dataclass
class RunResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    env_overrides: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run(argv: list[str], *, cwd: Path | None = None, timeout: int = 900) -> RunResult:
    """Run an argv ARRAY. Rejects a bare string outright so no caller can concatenate a command."""
    if isinstance(argv, str):  # type: ignore[unreachable]
        raise PluginError(
            "E_USAGE", "run() takes an argv array, never a command string"
        )
    if not argv or not all(isinstance(a, str) for a in argv):
        raise PluginError(
            "E_USAGE", f"argv must be a non-empty list of str, got {argv!r}"
        )
    env = dict(os.environ)
    overrides: dict[str, str] = {}
    if os.name == "nt" and _needs_pathconv_suppression(argv):
        overrides["MSYS_NO_PATHCONV"] = "1"
        env.update(overrides)
    try:
        cp = subprocess.run(  # noqa: S603 - argv array, shell=False by construction
            argv,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            env=env,
        )
    except FileNotFoundError as exc:
        raise PluginError("E_INTERP", f"executable not found: {argv[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise PluginError(
            "E_TXN", f"command timed out after {timeout}s: {argv[0]}"
        ) from exc
    return RunResult(
        list(argv), cp.returncode, cp.stdout or "", cp.stderr or "", overrides
    )


#: Windows CreateProcess caps the command line at 32,767 chars; a large inline prompt/arg dies
#: with OS error 206. Anything over this budget is marshalled through a file instead (IMP-0018).
ARG_BUDGET = 30000


def marshal_args(
    argv: list[str], payload: str, spill_dir: Path, *, flag: str
) -> list[str]:
    """Keep a big argument off the command line by spilling it to a file and passing the path."""
    if len(payload) + sum(len(a) + 1 for a in argv) < ARG_BUDGET:
        return [*argv, flag, payload]
    spill_dir.mkdir(parents=True, exist_ok=True)
    spill = spill_dir / "argspill.txt"
    spill.write_text(payload, encoding="utf-8", newline="\n")
    return [*argv, f"{flag}-file", str(spill)]


def launch_argv(
    interpreter: str, script: Path, args: list[str], *, os_name: str | None = None
) -> list[str]:
    """Per-OS launch adapter: the exact argv array that runs ``script`` on this platform.

    Windows/macOS/Linux differ in three ways that matter — the interpreter executable name,
    whether a wrapper flag set is required (``pwsh -File``), and whether the POSIX shebang is
    honoured at all (it is not, on Windows). The adapter resolves all three explicitly.
    """
    osn = os_name or current_os()
    if interpreter not in INTERPRETERS:
        raise PluginError(
            "E_INTERP", f"undeclared interpreter {interpreter!r} for {script.name}"
        )
    spec = INTERPRETERS[interpreter]
    names = spec.candidate_names(osn)
    if not names:
        raise PluginError(
            "E_COMPAT",
            f"no launch adapter for interpreter {interpreter!r} on {osn}",
            context={"interpreter": interpreter, "os": osn},
        )
    exe = names[0]
    if os.path.isabs(exe) and not Path(exe).exists():
        exe = names[1] if len(names) > 1 else exe
    resolved = shutil.which(exe) or exe
    return [resolved, *spec.exec_prefix, str(script), *args]
