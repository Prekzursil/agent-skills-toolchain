#!/usr/bin/env python3
"""AUD-0083 shared platform-interpreter resolver.

ONE resolver, imported by both probe2 (the real matrix build) and the
tests_required control (`control_windows_bare_vs_explicit.py`). The catalog's
control exists specifically to catch a resolver that silently reads the
shebang line instead of modelling what the OS actually does with a bare
invocation -- so the control MUST call this exact function, not a
reimplementation, or it proves nothing about this module.

WHAT IS MEASURED VS WHAT IS DOCUMENTED-BUT-SIMULATED (disclosed once, here,
rather than re-litigated at every call site):

  * linux:   real POSIX kernel shebang-exec behaviour. This substrate IS
             Linux, so the linux branch is checked against real subprocess
             execution in probe2 (fixture scripts actually run).
  * macos:   Darwin's kernel implements the same #! interpreter-dispatch
             mechanism as Linux (both derive from the BSD/SVR4 execve(2)
             convention for script magic numbers). No macOS hardware is
             available on this substrate, so this branch is INFERRED from
             that documented kernel-level equivalence, not measured on real
             macOS hardware. Flagged NOT-MEASURED in every row that uses it.
  * windows: Windows has NO kernel-level shebang support at all -- CreateProcess
             resolves an executable by extension (PATHEXT for extensionless
             bare names in cmd.exe) or by a registered file association, and
             a `#!` first line is just an ordinary text line to it. This
             branch is a CONTROLLED SIMULATION built from documented,
             citable Windows behaviour (see the docstrings on each helper
             below), never claimed as a real Windows host execution. It is
             the required substrate for AUD-0083's tests_required control.
"""

from __future__ import annotations

# Default Windows PATHEXT (cmd.exe / CreateProcess "which" search order when a
# bare name has no extension). Source: Microsoft docs, "PATHEXT" env var,
# stable across Windows 7 through 11. Notably: .PS1 and .SH are NOT members,
# and never have been -- this is the crux of the required control.
WINDOWS_PATHEXT = [
    ".COM",
    ".EXE",
    ".BAT",
    ".CMD",
    ".VBS",
    ".VBE",
    ".JS",
    ".JSE",
    ".WSF",
    ".WSH",
    ".MSC",
]

# Extensions with NO default Windows file-association that would make a bare
# `name.ext` invocation (with the extension typed explicitly, e.g.
# `script.sh` at a cmd.exe prompt) launch an interpreter automatically.
# `.py` is the one conditional exception: the python.org Windows installer
# registers a `Python.File` ftype + App Paths entry for `.py` by default
# (opt-out, but on by default since Python 3.3's PEP 397 launcher), so a bare
# `script.py` CAN resolve through `py.exe`. `py.exe` in turn DOES read the
# shebang line to select which installed Python version/interpreter to hand
# the script to (PEP 397) -- the one real exception to "Windows never reads
# shebangs" and precisely why this resolver is per-extension, not a single
# platform-wide switch.
WINDOWS_NO_ASSOCIATION_EXTENSIONS = {".sh", ".bash", ".zsh", ".ps1"}
WINDOWS_PY_LAUNCHER_ASSOCIATED = {".py"}
# .mjs/.js ARE handled on Windows by default, but by Windows Script Host
# (wscript/cscript), NOT Node.js -- WSH does not understand ES modules or
# Node's CommonJS globals, so this is not a working default execution path
# even though *something* runs. Modelled as FAILURE (wrong interpreter), not
# SUCCESS, because it does not produce the intended script's behaviour.
WINDOWS_WSH_MISASSOCIATED = {".js", ".mjs"}


def _windows_bare(ext: str, shebang_interpreter: str) -> dict:
    if ext in WINDOWS_PY_LAUNCHER_ASSOCIATED:
        return {
            "outcome": "SUCCESS",
            "interpreter": shebang_interpreter or "py.exe-default",
            "reason": (
                "py.exe (PEP 397 launcher), registered by the default "
                "python.org Windows installer as the .py file association, "
                "reads the shebang line to select the interpreter -- the "
                "one documented case where Windows honours a shebang. "
                "CONDITIONAL on that installer default not having been "
                "changed/opted out."
            ),
            "measured": "documented-conditional",
        }
    if ext in WINDOWS_WSH_MISASSOCIATED:
        return {
            "outcome": "FAILURE",
            "interpreter": "wscript.exe/cscript.exe (Windows Script Host)",
            "reason": (
                ".js/.mjs bare invocation resolves through the default "
                "Windows Script Host association, not Node.js; WSH cannot "
                "execute Node/ES-module syntax, so this is a wrong-"
                "interpreter failure even though *some* process launches."
            ),
            "measured": "documented",
        }
    if ext in WINDOWS_NO_ASSOCIATION_EXTENSIONS:
        return {
            "outcome": "FAILURE",
            "interpreter": None,
            "reason": (
                f"'{ext}' is not in PATHEXT and has no default Windows file "
                "association; cmd.exe reports "
                "\"'<name>' is not recognized as an internal or external "
                'command, operable program or batch file." (PowerShell: '
                "\"The term '...' is not recognized...\"). The shebang line "
                "is never inspected -- Windows has no kernel-level shebang "
                "support at all."
            ),
            "measured": "documented",
        }
    if ext == "":
        return {
            "outcome": "FAILURE",
            "interpreter": None,
            "reason": (
                "Extensionless bare invocation on Windows has zero "
                "interpreter-resolution mechanism by default (PATHEXT is "
                "extension-based); CreateProcess fails to find a matching "
                "executable."
            ),
            "measured": "documented",
        }
    return {
        "outcome": "FAILURE",
        "interpreter": None,
        "reason": f"'{ext}' has no modelled Windows association in this resolver.",
        "measured": "documented",
    }


def _windows_explicit(ext: str, explicit_interpreter: str) -> dict:
    """Explicit invocation, e.g. `bash script.sh` typed at a Windows shell.

    SUCCESS is conditional on `explicit_interpreter` actually being on PATH
    (e.g. Git for Windows ships `bash.exe`; WSL also provides one). The
    shebang line is IGNORED here by construction -- the caller told the OS
    exactly which interpreter to run, which is the whole point of the
    required control: an explicit invocation does not depend on Windows
    understanding the file at all.
    """
    return {
        "outcome": "SUCCESS",
        "interpreter": explicit_interpreter,
        "reason": (
            f"Explicit invocation names '{explicit_interpreter}' directly; "
            "CreateProcess resolves it via PATH like any other executable, "
            "conditional only on that interpreter being installed (e.g. "
            "Git for Windows / WSL provide bash.exe). The shebang line is "
            "never consulted."
        ),
        "measured": "documented-conditional",
    }


def _posix_bare(
    ext: str, has_shebang: bool, shebang_interpreter: str, exec_bit: bool, platform: str
) -> dict:
    measured = "measured" if platform == "linux" else "inferred-not-measured"
    if not exec_bit:
        return {
            "outcome": "FAILURE",
            "interpreter": None,
            "reason": "execve(2) refuses a file without the executable permission bit: Permission denied.",
            "measured": measured,
        }
    if has_shebang:
        return {
            "outcome": "SUCCESS",
            "interpreter": shebang_interpreter,
            "reason": (
                "The kernel's binfmt_script loader reads the '#!' first "
                "line and re-execs the named interpreter with this file as "
                "its argument."
            ),
            "measured": measured,
        }
    return {
        "outcome": "FAILURE",
        "interpreter": None,
        "reason": (
            "execve(2) with no recognised magic number (no shebang, not an "
            "ELF/Mach-O header) returns ENOEXEC. An interactive shell "
            "(bash/zsh) retries the same ENOEXEC child under /bin/sh as a "
            "compatibility fallback, but a raw execve()/subprocess call "
            "(no shell involved) does not -- this resolver models the "
            "shell-free case, i.e. what a CI runner's direct exec sees."
        ),
        "measured": measured,
    }


def _posix_explicit(explicit_interpreter: str) -> dict:
    return {
        "outcome": "SUCCESS",
        "interpreter": explicit_interpreter,
        "reason": (
            f"Explicit invocation runs '{explicit_interpreter}' directly "
            "via PATH lookup; the shebang line is never consulted, and the "
            "exec bit on the target script is irrelevant (it is opened as a "
            "data argument, not exec'd)."
        ),
        "measured": "measured" if explicit_interpreter else "documented",
    }


def resolve(
    *,
    ext: str,
    has_shebang: bool,
    shebang_interpreter: str,
    exec_bit: bool,
    platform: str,
    mode: str,
    explicit_interpreter: str = "",
) -> dict:
    """Resolve what would actually run a script.

    platform: 'linux' | 'macos' | 'windows'
    mode: 'bare' (e.g. `./script.sh` or `script.sh` with no interpreter
          named) | 'explicit' (e.g. `bash script.sh`)
    """
    if platform not in {"linux", "macos", "windows"}:
        raise ValueError(f"unknown platform {platform!r}")
    if mode not in {"bare", "explicit"}:
        raise ValueError(f"unknown mode {mode!r}")

    if platform == "windows":
        if mode == "bare":
            return _windows_bare(ext, shebang_interpreter)
        return _windows_explicit(
            ext, explicit_interpreter or shebang_interpreter or "bash"
        )

    # linux / macos share POSIX kernel exec semantics
    if mode == "bare":
        return _posix_bare(ext, has_shebang, shebang_interpreter, exec_bit, platform)
    return _posix_explicit(explicit_interpreter or shebang_interpreter or "bash")
