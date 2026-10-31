#!/usr/bin/env python3
"""Bounded, interpreter-explicit launcher for repository hook scripts.

``hookrun`` resolves one exact path beneath a hook root, selects the interpreter
from the file suffix, and otherwise stays transparent: the child inherits stdin,
stdout, stderr, environment, and the caller's working directory.

Usage::

    python hooks/_shared/hookrun.py [--root DIR] [--timeout SECONDS] HOOK [ARG ...]

There is deliberately no recursive discovery and no shell command string.  This
module launches ordinary lifecycle hooks, so their exit status remains authoritative;
work-unit artifact classification in ``completion.py`` is a separate, opt-in concern.
"""

from __future__ import annotations

import argparse
import math
import os
import shutil
import signal
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

HOOKS_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TIMEOUT_SECONDS = 30.0
EXIT_CANNOT_EXECUTE = 126
EXIT_NOT_FOUND = 127
EXIT_TIMEOUT = 124

_WINDOWS_GIT_BASH = (
    Path(r"C:\Program Files\Git\bin\bash.exe"),
    Path(r"C:\Program Files (x86)\Git\bin\bash.exe"),
)


class LaunchError(Exception):
    """A deterministic launcher failure with its command-line exit status."""

    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _positive_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return seconds


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one exact hook path with a bounded, explicit interpreter."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=HOOKS_ROOT,
        help="root containing the hook (default: parent of this _shared directory)",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_seconds,
        default=DEFAULT_TIMEOUT_SECONDS,
        metavar="SECONDS",
        help=f"wall-clock deadline (default: {DEFAULT_TIMEOUT_SECONDS:g})",
    )
    parser.add_argument("hook", help="root-relative hook path")
    parser.add_argument(
        "hook_args", nargs=argparse.REMAINDER, help="arguments for the hook"
    )
    return parser


def resolve_hook(root: Path, hook: str) -> Path:
    """Resolve one existing regular file beneath *root* without searching."""
    relative = Path(hook)
    if relative.is_absolute():
        raise LaunchError("hook path must be relative to --root", EXIT_CANNOT_EXECUTE)

    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise LaunchError(f"hook root is unavailable: {root}", EXIT_NOT_FOUND) from exc

    try:
        target = (resolved_root / relative).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise LaunchError(f"hook not found: {hook}", EXIT_NOT_FOUND) from exc

    try:
        target.relative_to(resolved_root)
    except ValueError as exc:
        raise LaunchError(
            f"hook escapes configured root: {hook}", EXIT_CANNOT_EXECUTE
        ) from exc
    if not target.is_file():
        raise LaunchError(f"hook is not a regular file: {hook}", EXIT_CANNOT_EXECUTE)
    return target


def find_bash(
    *,
    platform: str = sys.platform,
    is_file: Callable[[os.PathLike[str]], bool] = os.path.isfile,
    which: Callable[[str], str | None] = shutil.which,
) -> str | None:
    """Prefer Git Bash on Windows; PATH ``bash`` can be the incompatible WSL shim."""
    if platform == "win32":
        for candidate in _WINDOWS_GIT_BASH:
            if is_file(candidate):
                return str(candidate)
    candidate = which("bash")
    if platform == "win32" and candidate is not None:
        normalized = candidate.replace("\\", "/").casefold()
        if normalized.endswith("/windows/system32/bash.exe"):
            return None
    return candidate


def _runtime(
    name: str, which: Callable[[str], str | None] = shutil.which
) -> str | None:
    if name == "bash":
        return find_bash(which=which)
    if name == "powershell":
        return which("pwsh") or which("powershell")
    return which(name)


def build_command(
    hook: Path,
    hook_args: Sequence[str],
    *,
    which: Callable[[str], str | None] = shutil.which,
) -> list[str]:
    """Build a shell-free argv for a supported hook suffix."""
    suffix = hook.suffix.casefold()
    runtime_name: str | None
    prefix: list[str]
    if suffix == ".py":
        runtime_name = None
        prefix = [sys.executable]
    elif suffix in {".js", ".cjs", ".mjs"}:
        runtime_name = "node"
        prefix = []
    elif suffix == ".sh":
        runtime_name = "bash"
        prefix = []
    elif suffix == ".ps1":
        runtime_name = "powershell"
        prefix = []
    else:
        raise LaunchError(
            f"unsupported hook type {suffix or '<none>'}: {hook.name}",
            EXIT_CANNOT_EXECUTE,
        )

    if runtime_name is not None:
        runtime = _runtime(runtime_name, which)
        if runtime is None:
            raise LaunchError(
                f"required interpreter not found: {runtime_name}", EXIT_NOT_FOUND
            )
        prefix.append(runtime)
    if suffix == ".ps1":
        prefix.extend(
            ("-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File")
        )
    return [*prefix, str(hook), *hook_args]


def _start(command: Sequence[str]) -> subprocess.Popen[bytes]:
    options: dict[str, object] = {}
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)


def _reap_after_kill(process: subprocess.Popen[bytes]) -> bool:
    try:
        process.wait(timeout=5)
        return True
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=1)
        return True
    except subprocess.TimeoutExpired:
        return False


def _kill_process_tree(process: subprocess.Popen[bytes]) -> bool:
    tree_kill_confirmed = True
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5,
            )
            if result.returncode != 0:
                tree_kill_confirmed = False
                process.kill()
        except (OSError, subprocess.SubprocessError):
            tree_kill_confirmed = False
            try:
                process.kill()
            except OSError:
                pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            tree_kill_confirmed = False
            try:
                process.kill()
            except OSError:
                pass
    leader_reaped = _reap_after_kill(process)
    return tree_kill_confirmed and leader_reaped


def _shell_status(returncode: int) -> int:
    return 128 - returncode if returncode < 0 else returncode


def _install_signal_forwarders(
    process: subprocess.Popen[bytes],
) -> dict[signal.Signals, signal.Handlers]:
    previous: dict[signal.Signals, signal.Handlers] = {}

    def forward(signum: int, _frame: object) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            _kill_process_tree(process)
            return
        try:
            os.killpg(process.pid, signum)
        except OSError:
            process.send_signal(signum)

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, forward)
        except (OSError, RuntimeError, ValueError):
            previous.pop(signum, None)
    return previous


def _restore_signal_handlers(
    previous: dict[signal.Signals, signal.Handlers],
) -> None:
    for signum, handler in previous.items():
        try:
            signal.signal(signum, handler)
        except (OSError, RuntimeError, ValueError):
            pass


def launch(command: Sequence[str], timeout: float) -> tuple[int, bool, bool]:
    """Run *command* with inherited process context and a wall-clock deadline."""
    try:
        process = _start(command)
    except OSError as exc:
        raise LaunchError(f"could not start hook: {exc}", EXIT_NOT_FOUND) from exc
    previous = _install_signal_forwarders(process)
    try:
        return _shell_status(process.wait(timeout=timeout)), False, True
    except subprocess.TimeoutExpired:
        cleanup_confirmed = _kill_process_tree(process)
        return EXIT_TIMEOUT, True, cleanup_confirmed
    finally:
        _restore_signal_handlers(previous)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        hook = resolve_hook(args.root, args.hook)
        command = build_command(hook, args.hook_args)
        status, timed_out, cleanup_confirmed = launch(command, args.timeout)
    except LaunchError as exc:
        print(f"hookrun: {exc}", file=sys.stderr)
        return exc.exit_code
    if timed_out:
        cleanup_note = "" if cleanup_confirmed else " (process cleanup unconfirmed)"
        print(
            f"hookrun: timed out after {args.timeout:g}s: {args.hook}{cleanup_note}",
            file=sys.stderr,
        )
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
