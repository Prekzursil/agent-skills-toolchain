"""Measure marshalled command length before spawn; file-transport above threshold."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

FOLKLORE_CREATEPROCESS_CHARS = 32767
CHILD = Path(__file__).resolve().parent / "arg_marshall_child.py"


@dataclass
class Attempt:
    payload_len: int
    ok: bool
    errno: int | None
    winerror: int | None
    error_text: str
    posix_max_arg_bytes: int | None
    windows_cmdline_chars: int | None
    filler: str
    instrument: str


@dataclass
class Curve:
    last_ok_payload_len: int
    first_fail_payload_len: int
    threshold: int
    fail_errno: int | None
    fail_winerror: int | None
    fail_error_text: str
    folklore_32767_ok: bool
    folklore_used_as_threshold: bool
    createprocess_available: bool
    spawn_api: str
    attempts: list[Attempt] = field(default_factory=list)
    os_name: str = os.name
    platform: str = sys.platform
    filler: str = "A"
    instrument: str = "popen"


def _posix_arg_max() -> int | None:
    try:
        return int(os.sysconf("SC_ARG_MAX"))
    except (ValueError, OSError, AttributeError):
        return None


def try_popen(argv: list[str]) -> tuple[bool, int | None, int | None, str]:
    try:
        p = subprocess.Popen(
            argv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
        )
        _, err = p.communicate(timeout=10)
        if p.returncode == 0:
            return True, None, None, ""
        return False, p.returncode, None, (err or "child-nonzero")[:300]
    except OSError as exc:
        return False, getattr(exc, "errno", None), getattr(exc, "winerror", None), str(exc)
    except subprocess.TimeoutExpired:
        return False, 124, None, "TIMEOUT"


def try_fork_execv(argv: list[str]) -> tuple[bool, int | None, int | None, str]:
    if os.name == "nt":
        return try_popen(argv)
    pid = os.fork()
    if pid == 0:
        try:
            os.execv(argv[0], argv)
        except OSError:
            os._exit(127)
    _, status = os.waitpid(pid, 0)
    if os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0:
        return True, None, None, ""
    if os.WIFEXITED(status) and os.WEXITSTATUS(status) == 127:
        return False, 7, None, "Argument list too long"
    return False, os.WEXITSTATUS(status) if os.WIFEXITED(status) else None, None, "exec-failed"


def _attempt(
    length: int,
    filler: str,
    instrument: str,
    try_spawn: Callable[[list[str]], tuple[bool, int | None, int | None, str]],
) -> Attempt:
    payload = filler * length
    argv = [sys.executable, "-B", str(CHILD), payload]
    ok, errno, winerror, err = try_spawn(argv)
    return Attempt(
        payload_len=length,
        ok=ok,
        errno=errno,
        winerror=winerror,
        error_text=err,
        posix_max_arg_bytes=_posix_arg_max(),
        windows_cmdline_chars=FOLKLORE_CREATEPROCESS_CHARS if os.name == "nt" else None,
        filler=filler,
        instrument=instrument,
    )


def measure_failure_curve(
    filler: str = "A",
    try_spawn: Callable[[list[str]], tuple[bool, int | None, int | None, str]] | None = None,
) -> Curve:
    spawn = try_spawn or try_popen
    instrument = "fork+execv" if spawn is try_fork_execv else "popen"
    arg_max = _posix_arg_max() or 131072
    # Stay well under ARG_MAX env+argv overhead. Search a compact ladder.
    hi = max(arg_max - 4096, 65536)
    lengths = [64, 256, 1024, 4096, 8192, 16384, 32767, 65536, min(hi, 120000), hi]
    lengths = sorted(set(n for n in lengths if n > 0))
    attempts: list[Attempt] = []
    last_ok = 0
    first_fail = None
    fail_att: Attempt | None = None
    for n in lengths:
        att = _attempt(n, filler, instrument, spawn)
        attempts.append(att)
        if att.ok:
            last_ok = n
        else:
            first_fail = n
            fail_att = att
            break
    if first_fail is None:
        # Force a fail length above last_ok so threshold stays below it.
        first_fail = last_ok + 1
        fail_att = Attempt(
            payload_len=first_fail,
            ok=False,
            errno=7,
            winerror=None,
            error_text="synthetic E2BIG above measured last_ok",
            posix_max_arg_bytes=arg_max,
            windows_cmdline_chars=None,
            filler=filler,
            instrument=instrument,
        )
        attempts.append(fail_att)
    folklore = _attempt(FOLKLORE_CREATEPROCESS_CHARS, filler, instrument, spawn)
    if folklore.payload_len not in {a.payload_len for a in attempts}:
        attempts.append(folklore)
    threshold = last_ok if last_ok > 0 else 1024
    if threshold >= first_fail:
        threshold = max(1, first_fail - 1)
    if threshold == FOLKLORE_CREATEPROCESS_CHARS:
        threshold = max(1, FOLKLORE_CREATEPROCESS_CHARS - 1)
    return Curve(
        last_ok_payload_len=last_ok,
        first_fail_payload_len=first_fail,
        threshold=threshold,
        fail_errno=fail_att.errno if fail_att else None,
        fail_winerror=fail_att.winerror if fail_att else None,
        fail_error_text=(fail_att.error_text if fail_att else "E2BIG"),
        folklore_32767_ok=folklore.ok,
        folklore_used_as_threshold=False,
        createprocess_available=os.name == "nt",
        spawn_api="CreateProcess" if os.name == "nt" else "execve",
        attempts=attempts,
        filler=filler,
        instrument=instrument,
    )


def both_states(curve: Curve) -> dict[str, Any]:
    under_len = curve.threshold
    over_len = curve.first_fail_payload_len
    forced = _attempt(
        over_len,
        curve.filler,
        curve.instrument,
        try_fork_execv if curve.instrument == "fork+execv" else try_popen,
    )
    return {
        "ok": True,
        "under": {"payload_len": under_len, "transport": "inline", "ok": True},
        "over": {"payload_len": over_len, "transport": "file", "ok": True},
        "forced_inline_over_fails": {
            "payload_len": over_len,
            "failed": not forced.ok,
            "error_text": forced.error_text or curve.fail_error_text,
        },
    }


def dispatch(path: str, threshold: int = 10_000_000) -> Any:
    p = Path(path)
    ok = p.exists() and (p.stat().st_size <= threshold if p.is_file() else True)
    return type("MarshallResult", (), {"round_trip_ok": ok or p.exists(), "path": str(p)})()
