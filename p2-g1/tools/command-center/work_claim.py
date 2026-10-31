"""Crash-safe exclusive work-claim protocol (IMP-0409).

Acquire writes claim JSON to a unique tmp file, fsyncs, then publishes with
renameat2(RENAME_NOREPLACE) onto <claims_dir>/<unit_id>.json so two sessions
cannot both hold the same unit. Holder renew overwrites expires_at_unix via
tmp+os.replace. Holder release unlinks. SIGKILL of the holder leaves the
file; TTL (expires_at_unix vs time.time()) is what lets a challenger in.

The mutation control replaces exclusive renameat2 with dest.exists()+write_bytes
so the N=50 concurrency test turns red (many GRANTED).
"""
from __future__ import annotations

import ctypes
import errno
import json
import os
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

GRANTED = "GRANTED"
DENIED = "DENIED"
ALREADY_HELD = "ALREADY_HELD"
NOT_HOLDER = "NOT_HOLDER"
NO_CLAIM = "NO_CLAIM"

PUBLISH_EXCLUSIVE = "exclusive"
PUBLISH_MUTANT = "mutant"

_AT_FDCWD = -100
_RENAME_NOREPLACE = 1  # linux/fs.h

if os.name == "nt":
    _LIBC = None  # Windows: exclusive-create publish (see _renameat2_noreplace)
else:
    _LIBC = ctypes.CDLL("libc.so.6", use_errno=True)
if _LIBC is not None:
    _LIBC.renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    _LIBC.renameat2.restype = ctypes.c_int


def _renameat2_noreplace(src: Path, dst: Path) -> None:
    """Atomic exclusive publish.

    POSIX: renameat2(2) with RENAME_NOREPLACE (certified path, unchanged).
    Windows: O_CREAT|O_EXCL create is the equivalent exclusive primitive -
    exactly one concurrent creator wins, all others get FileExistsError.
    """
    if os.name != "nt" and _LIBC is not None:
        rc = _LIBC.renameat2(
            _AT_FDCWD,
            os.fsencode(os.fspath(src)),
            _AT_FDCWD,
            os.fsencode(os.fspath(dst)),
            _RENAME_NOREPLACE,
        )
        if rc == 0:
            return
        err = ctypes.get_errno()
        if err == errno.EEXIST:
            raise FileExistsError(err, os.strerror(err), str(dst))
        raise OSError(err, os.strerror(err), str(src), str(dst))
    payload = src.read_bytes()
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(os.fspath(dst), flags)
    except FileExistsError:
        raise
    except OSError as exc:
        raise OSError(
            exc.errno or 0,
            os.strerror(exc.errno) if exc.errno else "exclusive publish failed",
            str(dst),
        ) from exc
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    src.unlink(missing_ok=True)


def _fsync_dir(directory: Path) -> None:
    if os.name == "nt":
        return  # Windows: best-effort skipped; the claim write itself is fsynced
    fd = os.open(os.fspath(directory), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_tmp(directory: Path, stem: str, payload: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / f".{stem}.{os.getpid()}.{time.time_ns()}.tmp"
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    return tmp


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _expired(claim: dict[str, Any], now: float | None = None) -> bool:
    now = time.time() if now is None else now
    expires = float(claim.get("expires_at_unix") or 0)
    return expires <= now


def _claim_path(claims_dir: Path, unit_id: str) -> Path:
    return claims_dir / f"{unit_id}.json"


def _result(
    status: str,
    session_id: str,
    *,
    reason_code: str | None = None,
    fencing_token: int | None = None,
    claim: dict[str, Any] | None = None,
    unit_id: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "reason_code": reason_code,
        "session_id": session_id,
        "fencing_token": fencing_token,
        "claim": claim,
        "unit_id": unit_id,
    }


def _retire_expired(dest: Path) -> dict[str, Any] | None:
    """Move an expired claim aside. First rename wins; losers retry."""
    current = _read_json(dest)
    if current is None:
        return None
    if not _expired(current):
        return None
    retired = dest.with_name(f".{dest.name}.retired.{os.getpid()}.{time.time_ns()}")
    try:
        os.rename(dest, retired)
    except FileNotFoundError:
        return None
    except OSError:
        return None
    return current


def acquire(
    claims_dir: Path | str,
    unit_id: str,
    session_id: str,
    ttl_seconds: float = 300.0,
    *,
    publish: str = PUBLISH_EXCLUSIVE,
) -> dict[str, Any]:
    """Publish a per-unit claim. exclusive publish is renameat2 NOREPLACE."""
    claims_dir = Path(claims_dir)
    claims_dir.mkdir(parents=True, exist_ok=True)
    dest = _claim_path(claims_dir, unit_id)
    ttl_seconds = float(ttl_seconds)

    if publish == PUBLISH_MUTANT:
        now = time.time()
        payload = {
            "unit_id": unit_id,
            "session_id": session_id,
            "fencing_token": 1,
            "acquired_at_unix": now,
            "expires_at_unix": now + ttl_seconds,
            "status": GRANTED,
        }
        _ = dest.exists()
        dest.write_bytes(
            (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
        return _result(
            GRANTED,
            session_id,
            fencing_token=1,
            claim=payload,
            unit_id=unit_id,
        )

    for _ in range(64):
        now = time.time()
        current = _read_json(dest)
        token = 1
        if current is not None and not _expired(current, now):
            return _result(
                DENIED,
                session_id,
                reason_code=ALREADY_HELD,
                fencing_token=int(current.get("fencing_token") or 1),
                claim=current,
                unit_id=unit_id,
            )
        if current is not None and _expired(current, now):
            stolen = _retire_expired(dest)
            if stolen is None:
                continue
            token = int(stolen.get("fencing_token") or 0) + 1
        payload = {
            "unit_id": unit_id,
            "session_id": session_id,
            "fencing_token": token,
            "acquired_at_unix": now,
            "expires_at_unix": now + ttl_seconds,
            "status": GRANTED,
        }
        tmp = _write_tmp(claims_dir, f"{unit_id}.{session_id}", payload)
        try:
            _renameat2_noreplace(tmp, dest)
            tmp = None
            _fsync_dir(claims_dir)
            return _result(
                GRANTED,
                session_id,
                fencing_token=token,
                claim=payload,
                unit_id=unit_id,
            )
        except FileExistsError:
            holder = _read_json(dest)
            if holder is not None and not _expired(holder):
                return _result(
                    DENIED,
                    session_id,
                    reason_code=ALREADY_HELD,
                    fencing_token=int(holder.get("fencing_token") or 1),
                    claim=holder,
                    unit_id=unit_id,
                )
            continue
        finally:
            if tmp is not None:
                Path(tmp).unlink(missing_ok=True)
    holder = _read_json(dest) or {}
    return _result(
        DENIED,
        session_id,
        reason_code=ALREADY_HELD,
        fencing_token=int(holder.get("fencing_token") or 1),
        claim=holder or None,
        unit_id=unit_id,
    )


def renew(
    claims_dir: Path | str,
    unit_id: str,
    session_id: str,
    ttl_seconds: float = 300.0,
) -> dict[str, Any]:
    """Holder-only overwrite of expires_at_unix via tmp+os.replace."""
    claims_dir = Path(claims_dir)
    dest = _claim_path(claims_dir, unit_id)
    current = _read_json(dest)
    if current is None:
        return _result(DENIED, session_id, reason_code=NO_CLAIM, unit_id=unit_id)
    if str(current.get("session_id") or "") != session_id:
        return _result(
            DENIED,
            session_id,
            reason_code=NOT_HOLDER,
            fencing_token=int(current.get("fencing_token") or 1),
            claim=current,
            unit_id=unit_id,
        )
    now = time.time()
    updated = dict(current)
    updated["expires_at_unix"] = now + float(ttl_seconds)
    updated["renewed_at_unix"] = now
    tmp = _write_tmp(claims_dir, f"{unit_id}.renew.{session_id}", updated)
    os.replace(tmp, dest)
    _fsync_dir(claims_dir)
    return _result(
        GRANTED,
        session_id,
        fencing_token=int(updated.get("fencing_token") or 1),
        claim=updated,
        unit_id=unit_id,
    )


def release(
    claims_dir: Path | str,
    unit_id: str,
    session_id: str,
) -> dict[str, Any]:
    """Holder-only unlink of the claim file."""
    claims_dir = Path(claims_dir)
    dest = _claim_path(claims_dir, unit_id)
    current = _read_json(dest)
    if current is None:
        return _result(DENIED, session_id, reason_code=NO_CLAIM, unit_id=unit_id)
    if str(current.get("session_id") or "") != session_id:
        return _result(
            DENIED,
            session_id,
            reason_code=NOT_HOLDER,
            fencing_token=int(current.get("fencing_token") or 1),
            claim=current,
            unit_id=unit_id,
        )
    dest.unlink(missing_ok=True)
    return _result(
        GRANTED,
        session_id,
        fencing_token=int(current.get("fencing_token") or 1),
        claim=current,
        unit_id=unit_id,
    )


def _attempt_row(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "fencing_token": result.get("fencing_token"),
        "reason_code": result.get("reason_code"),
        "session_id": result.get("session_id"),
        "status": result.get("status"),
    }


def run_concurrent_acquire(
    root: Path | str,
    unit_id: str,
    n: int = 50,
    *,
    ttl_seconds: float = 300.0,
    publish: str = PUBLISH_EXCLUSIVE,
) -> dict[str, Any]:
    """N concurrent acquire attempts on one unit id. Honest path: exactly 1 grant."""
    root = Path(root)
    claims_dir = root / "claims"
    claims_dir.mkdir(parents=True, exist_ok=True)
    n = int(n)
    sessions = [f"sess-{i:03d}" for i in range(n)]
    barrier = threading.Barrier(n)
    ordered: dict[str, dict[str, Any]] = {}

    def worker(session_id: str) -> tuple[str, dict[str, Any]]:
        barrier.wait(timeout=30)
        return session_id, acquire(
            claims_dir,
            unit_id,
            session_id,
            ttl_seconds=ttl_seconds,
            publish=publish,
        )

    with ThreadPoolExecutor(max_workers=n) as pool:
        futs = [pool.submit(worker, sid) for sid in sessions]
        for fut in as_completed(futs):
            sid, result = fut.result()
            ordered[sid] = result

    attempts = [_attempt_row(ordered[sid]) for sid in sessions]
    granted_rows = [a for a in attempts if a["status"] == GRANTED]
    denied_rows = [a for a in attempts if a["status"] == DENIED]
    reason_counts: dict[str, int] = {}
    for row in denied_rows:
        code = str(row.get("reason_code") or "")
        reason_counts[code] = reason_counts.get(code, 0) + 1
    holder = granted_rows[0]["session_id"] if granted_rows else None
    return {
        "n": n,
        "granted": len(granted_rows),
        "denied": len(denied_rows),
        "reason_counts": reason_counts,
        "attempts": attempts,
        "holder_session_id": holder,
        "publish": publish,
        "unit_id": unit_id,
    }


def run_crash_ttl(root: Path | str, ttl_seconds: float = 0.6) -> dict[str, Any]:
    """Holder SIGKILL leaves the claim file; TTL then lets a challenger in."""
    root = Path(root)
    claims_dir = root / "claims"
    claims_dir.mkdir(parents=True, exist_ok=True)
    ready = root / "holder-ready.json"
    unit_id = "IMP-0409"
    holder_session = "holder-killed"
    ttl_seconds = float(ttl_seconds)
    tools_cc = str(Path(__file__).resolve().parent)
    snippet = (
        "import json, sys, time\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import work_claim as wc\n"
        "claims, unit, session, ttl, ready = sys.argv[2:7]\n"
        "r = wc.acquire(Path(claims), unit, session, ttl_seconds=float(ttl))\n"
        "Path(ready).write_text(json.dumps(r), encoding='utf-8')\n"
        "time.sleep(3600)\n"
    )
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-c",
            snippet,
            tools_cc,
            str(claims_dir),
            unit_id,
            holder_session,
            str(ttl_seconds),
            str(ready),
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline and not ready.is_file():
        time.sleep(0.02)
        if proc.poll() is not None:
            break
    holder_grant = _read_json(ready) or {}
    if proc.pid:
        _sigkill = getattr(signal, "SIGKILL", None)
        if _sigkill is not None:
            os.kill(proc.pid, _sigkill)
        else:
            proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    dest = _claim_path(claims_dir, unit_id)
    claim_present_after_kill = dest.is_file()
    before = acquire(claims_dir, unit_id, "challenger-before-ttl", ttl_seconds=30.0)
    time.sleep(ttl_seconds + 0.35)
    after = acquire(claims_dir, unit_id, "challenger-after-ttl", ttl_seconds=30.0)
    passed = bool(
        holder_grant.get("status") == GRANTED
        and claim_present_after_kill
        and before.get("status") == DENIED
        and before.get("reason_code") == ALREADY_HELD
        and after.get("status") == GRANTED
        and ((after.get("claim") or {}).get("session_id") == "challenger-after-ttl")
    )
    return {
        "pass": passed,
        "ttl_seconds": ttl_seconds,
        "claim_present_after_kill": claim_present_after_kill,
        "holder_grant": holder_grant,
        "challenger_before_ttl": before,
        "challenger_after_ttl": after,
        "unit_id": unit_id,
    }


def run_mutation_control(root: Path | str, n: int = 50) -> dict[str, Any]:
    """Honest exclusive rename grants 1; dest.exists()+write_bytes turns red."""
    root = Path(root)
    honest = run_concurrent_acquire(
        root / "honest", "IMP-0409", n=n, publish=PUBLISH_EXCLUSIVE
    )
    mutant = run_concurrent_acquire(
        root / "mutant", "IMP-0409", n=n, publish=PUBLISH_MUTANT
    )
    honest_ok = honest["granted"] == 1 and honest["denied"] == n - 1
    mutant_red = mutant["granted"] != 1
    return {
        "pass": bool(honest_ok and mutant_red),
        "honest_ok": honest_ok,
        "honest": {
            "granted": honest["granted"],
            "denied": honest["denied"],
            "reason_counts": honest["reason_counts"],
        },
        "mutant_atomic_rename_removed": {
            "granted": mutant["granted"],
            "denied": mutant["denied"],
            "reason_counts": mutant["reason_counts"],
        },
        "mutant_turns_concurrency_red": mutant_red,
        "n": n,
    }
