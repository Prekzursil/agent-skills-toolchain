"""Live escalating-payload spawn measurement on THIS host.

Does not use the documented Windows 32767 CreateProcess cap as the failure
threshold. A runtime not spawned is NOT-CHECKED. Error strings are quoted
from OSError/stderr. Does not print environment values that look like secrets.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
MAX_PROBE = 8 * 1024 * 1024
VENDOR_CANDIDATES = (
    "claude",
    "codex",
    "cursor",
    "agent",
    "gemini",
    "copilot",
    "pwsh",
    "powershell",
    "aider",
    "goose",
)
CHILD = "import json,sys; print(json.dumps({'n': len(sys.argv[-1]) if len(sys.argv)>1 else 0}))"
SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*\S+"
)


def redact(text: str) -> str:
    return SECRET_RE.sub(r"\1=REDACTED", text or "")


def clean_env() -> dict[str, str]:
    keep = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "USER": os.environ.get("USER", "probe"),
        "LANG": "C",
        "LC_ALL": "C",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    tmp = os.environ.get("TMPDIR")
    if tmp:
        keep["TMPDIR"] = tmp
    return keep


def host_limits() -> dict[str, Any]:
    import platform

    getconf = None
    try:
        p = subprocess.run(
            ["getconf", "ARG_MAX"],
            capture_output=True,
            text=True,
            timeout=5,
            env=clean_env(),
        )
        if p.returncode == 0:
            getconf = int((p.stdout or "").strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        getconf = None
    xargs = None
    try:
        p = subprocess.run(
            ["xargs", "--show-limits"],
            capture_output=True,
            text=True,
            timeout=5,
            env=clean_env(),
            input="",
        )
        xargs = redact((p.stderr or "") + (p.stdout or ""))[-1500:]
    except (OSError, subprocess.TimeoutExpired):
        xargs = None
    uname = platform.uname()
    return {
        "sys_platform": sys.platform,
        "os_name": os.name,
        "system": uname.system,
        "release": uname.release,
        "machine": uname.machine,
        "getconf_ARG_MAX": getconf,
        "xargs_show_limits": xargs,
        "windows_createprocess_32767": "NOT-CHECKED",
        "windows_createprocess_reason": (
            "host is Linux; CreateProcessW / OS error 206 cannot be spawned here"
        ),
    }


def try_spawn(argv: list[str], timeout: float) -> dict[str, Any]:
    try:
        p = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=clean_env(),
        )
        child_n = None
        try:
            child_n = json.loads((p.stdout or "").strip() or "null")
            if isinstance(child_n, dict):
                child_n = child_n.get("n")
            else:
                child_n = None
        except json.JSONDecodeError:
            child_n = None
        return {
            "spawned": True,
            "timeout": False,
            "rc": p.returncode,
            "errno": None,
            "error": None,
            "stderr": redact(p.stderr or "")[-400:],
            "child_n": child_n,
        }
    except subprocess.TimeoutExpired:
        return {
            "spawned": True,
            "timeout": True,
            "rc": None,
            "errno": None,
            "error": "TIMEOUT after process start (invocation path accepted the argv)",
            "stderr": "",
            "child_n": None,
        }
    except OSError as exc:
        err = f"OSError: [Errno {exc.errno}] {exc.strerror}"
        return {
            "spawned": False,
            "timeout": False,
            "rc": None,
            "errno": exc.errno,
            "error": err,
            "stderr": redact(str(exc))[-400:],
            "child_n": None,
        }


def python_argv(n: int) -> list[str]:
    return [sys.executable, "-c", CHILD, "P" * n]


def true_argv(n: int) -> list[str]:
    return ["/bin/true", "P" * n]


def vendor_argv(binary: str, n: int) -> list[str]:
    # --version keeps this an argv-limit probe, not a billed session start.
    return [binary, "--version", "P" * n]


def search_limit(
    builder: Callable[[int], list[str]],
    *,
    timeout: float,
    cap: int = MAX_PROBE,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    last_ok = 0
    last_ok_child_n = None
    first_fail: int | None = None
    first_fail_error = None
    first_fail_errno = None

    def one(n: int) -> dict[str, Any]:
        row = try_spawn(builder(n), timeout)
        attempts.append(
            {
                "n": n,
                "spawned": row["spawned"],
                "timeout": row["timeout"],
                "errno": row["errno"],
                "error": row["error"],
                "rc": row["rc"],
                "child_n": row["child_n"],
            }
        )
        return row

    n = 1
    while n <= cap:
        row = one(n)
        if row["spawned"]:
            last_ok = n
            last_ok_child_n = row.get("child_n")
            n = n * 2
            continue
        first_fail = n
        first_fail_error = row.get("error")
        first_fail_errno = row.get("errno")
        break
    if first_fail is None:
        return {
            "last_ok_bytes": last_ok,
            "first_fail_bytes": None,
            "first_fail_error": None,
            "first_fail_errno": None,
            "last_ok_child_n": last_ok_child_n,
            "truncated": (
                last_ok_child_n is not None and int(last_ok_child_n) != last_ok
            ),
            "fail_mode": "no-failure-at-cap",
            "attempts": attempts,
        }

    lo, hi = last_ok, first_fail
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        row = one(mid)
        if row["spawned"]:
            lo = mid
            last_ok = mid
            last_ok_child_n = row.get("child_n")
        else:
            hi = mid
            first_fail = mid
            first_fail_error = row.get("error")
            first_fail_errno = row.get("errno")

    truncated = last_ok_child_n is not None and int(last_ok_child_n) != last_ok
    if first_fail_errno == 7:
        fail_mode = "loud-e2big"
    elif first_fail_error:
        fail_mode = "loud-oserror"
    else:
        fail_mode = "unknown"
    return {
        "last_ok_bytes": last_ok,
        "first_fail_bytes": first_fail,
        "first_fail_error": first_fail_error,
        "first_fail_errno": first_fail_errno,
        "last_ok_child_n": last_ok_child_n,
        "truncated": truncated,
        "fail_mode": fail_mode,
        "attempts": attempts,
    }


def file_transport(size: int, tmp: Path, timeout: float) -> dict[str, Any]:
    tmp.mkdir(parents=True, exist_ok=True)
    blob = tmp / "payload.bin"
    blob.write_bytes(b"P" * size)
    argv = [sys.executable, "-B", str(HERE / "escalate.py"), "--read-file", str(blob)]
    row = try_spawn(argv, timeout)
    return {
        "size": size,
        "argv_chars": sum(len(a) for a in argv),
        "spawned": row["spawned"],
        "timeout": row["timeout"],
        "error": row["error"],
        "child_n": row.get("child_n"),
        "rc": row.get("rc"),
    }


def discover() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "id": "python3",
            "kind": "posix-exec",
            "present": True,
            "path": sys.executable,
            "timeout": 2.0,
        },
        {
            "id": "posix-true",
            "kind": "posix-exec",
            "present": Path("/bin/true").is_file(),
            "path": "/bin/true",
            "timeout": 2.0,
        },
    ]
    for name in VENDOR_CANDIDATES:
        path = shutil.which(name)
        rows.append(
            {
                "id": name,
                "kind": "vendor-cli",
                "present": bool(path),
                "path": path,
                "timeout": 1.5,
            }
        )
    return rows


def builder_for(row: dict[str, Any]) -> Callable[[int], list[str]] | None:
    if not row.get("present"):
        return None
    if row["id"] == "python3":
        return python_argv
    if row["id"] == "posix-true":
        return true_argv
    if row.get("path"):
        return lambda n, p=row["path"]: vendor_argv(str(p), n)
    return None


def measure_all(tmp: Path) -> dict[str, Any]:
    started = time.perf_counter()
    host = host_limits()
    runtimes: list[dict[str, Any]] = []
    n_attempts = 0
    for row in discover():
        rec = {
            "id": row["id"],
            "kind": row["kind"],
            "present": row["present"],
            "path": row["path"],
            "status": "NOT-CHECKED",
        }
        builder = builder_for(row)
        if builder is None:
            rec["reason"] = "binary not on PATH; not assumed to match another runtime"
            runtimes.append(rec)
            continue
        curve = search_limit(builder, timeout=float(row["timeout"]))
        n_attempts += len(curve.get("attempts") or [])
        rec.update(curve)
        rec["status"] = "MEASURED"
        rec["loud_or_truncate"] = (
            "truncate" if curve.get("truncated") else curve.get("fail_mode")
        )
        runtimes.append(rec)

    measured = [r for r in runtimes if r.get("status") == "MEASURED" and r.get("first_fail_bytes")]
    ten_x = None
    file_row = None
    if measured:
        ten_x = max(int(r["first_fail_bytes"]) for r in measured) * 10
        ten_x = min(ten_x, 12 * 1024 * 1024)
        file_row = file_transport(ten_x, tmp, timeout=5.0)

    elapsed = time.perf_counter() - started
    return {
        "host": host,
        "runtimes": runtimes,
        "sample_size": n_attempts + (1 if file_row else 0),
        "elapsed_seconds": elapsed,
        "file_transport": file_row,
        "file_transport_size": ten_x,
    }


def confirm_bounds(row_spec: dict[str, Any], last_ok: int, first_fail: int) -> dict[str, Any]:
    builder = builder_for(row_spec)
    if builder is None:
        return {"ok": False, "reason": "absent"}
    timeout = float(row_spec.get("timeout") or 2.0)
    ok_row = try_spawn(builder(last_ok), timeout)
    fail_row = try_spawn(builder(first_fail), timeout)
    return {
        "ok": bool(ok_row.get("spawned")) and (not fail_row.get("spawned")),
        "last_ok_spawned": ok_row.get("spawned"),
        "last_ok_child_n": ok_row.get("child_n"),
        "first_fail_spawned": fail_row.get("spawned"),
        "first_fail_error": fail_row.get("error"),
        "first_fail_errno": fail_row.get("errno"),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--read-file"] and len(argv) >= 2:
        data = Path(argv[1]).read_bytes()
        print(json.dumps({"n": len(data)}, sort_keys=True))
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
