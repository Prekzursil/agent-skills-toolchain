"""Crash-safe exclusive work-claim protocol (IMP-0409).

Acquire writes claim JSON to a unique tmp file, fsyncs, then publishes with
renameat2(RENAME_NOREPLACE) onto <claims_dir>/<unit_id>.json so two sessions
cannot both hold the same unit. Holder renew overwrites expires_at_unix via
tmp+os.replace. Holder release unlinks. SIGKILL of the holder leaves the
file; TTL (expires_at_unix vs time.time()) is what lets a challenger in.

The mutation control replaces exclusive renameat2 with dest.exists()+write_bytes
so the N=50 concurrency test turns red (many GRANTED).

Execute-once dispatch (TST-0157, ADV-0126) is the layer above: ``dispatch``
claims <root>/claims/<unit_id>.dispatch with O_EXCL, runs the unit once, writes
one execution record and one receipt (<root>/receipts/<unit_id>.json), and
types every later or concurrent caller DUPLICATE-SUPPRESSED.  A receipt is
permanent (no TTL: a finished unit never re-runs); a failure between claim and
receipt propagates loudly and frees the claim so a retry can execute.  The
check-then-act mutant (``atomic=False``) is the TOCTOU control that must
double-grant.
"""
from __future__ import annotations

import ctypes
import errno
import hashlib
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

_LIBC = ctypes.CDLL("libc.so.6", use_errno=True)
_LIBC.renameat2.argtypes = [
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.c_uint,
]
_LIBC.renameat2.restype = ctypes.c_int


def _renameat2_noreplace(src: Path, dst: Path) -> None:
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


def _fsync_dir(directory: Path) -> None:
    fd = os.open(os.fspath(directory), os.O_RDONLY | os.O_DIRECTORY)
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
        os.kill(proc.pid, signal.SIGKILL)
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


# --------------------------------------------------------------------------- execute-once dispatch
#
# Layout under <root> (``prepare`` creates it; ``dispatch`` creates it lazily):
#     claims/<unit_id>.dispatch            winner's claim marker, created with O_EXCL
#     executions/<unit_id>/<session>.json  one record per execution actually performed
#     receipts/<unit_id>.json              the single receipt (tmp + fsync + rename)
#
# ``count_executions`` counts what really ran (the mutant path yields 2);
# ``count_receipts`` counts what was published (always at most 1 file per id).

EXECUTED = "EXECUTED"
DUPLICATE_SUPPRESSED = "DUPLICATE-SUPPRESSED"
ALREADY_EXECUTED = "ALREADY_EXECUTED"
CLAIM_IN_PROGRESS = "CLAIM_IN_PROGRESS"
RECEIPT_SCHEMA = "command-center.dispatch-receipt/v1"

CLAIMS_SUBDIR = "claims"
RECEIPTS_SUBDIR = "receipts"
EXECUTIONS_SUBDIR = "executions"


def _check_id(value: object, what: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value in (".", "..")
        or any(ch in value for ch in ("/", "\\", "\0"))
    ):
        raise ValueError(f"{what} must be a non-empty string without path separators: {value!r}")
    return value


def _json_bytes(doc: Any) -> bytes:
    try:
        return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TypeError(f"dispatch payload and result must be JSON-serialisable: {exc}") from exc


def _payload_digest(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def prepare(root: Path | str) -> dict[str, Path]:
    """Create the dispatch layout under ``root`` and return its directories."""
    root = Path(root)
    layout = {
        "root": root,
        "claims": root / CLAIMS_SUBDIR,
        "receipts": root / RECEIPTS_SUBDIR,
        "executions": root / EXECUTIONS_SUBDIR,
    }
    for key in ("claims", "receipts", "executions"):
        layout[key].mkdir(parents=True, exist_ok=True)
    return layout


def receipt_path(root: Path | str, unit_id: str) -> Path:
    """Where the single receipt of ``unit_id`` lives once it has executed."""
    return Path(root) / RECEIPTS_SUBDIR / f"{_check_id(unit_id, 'unit_id')}.json"


def claim_marker_path(root: Path | str, unit_id: str) -> Path:
    """The O_EXCL claim marker of ``unit_id``."""
    return Path(root) / CLAIMS_SUBDIR / f"{_check_id(unit_id, 'unit_id')}.dispatch"


def executions_dir(root: Path | str, unit_id: str) -> Path:
    """Directory holding one record per execution of ``unit_id`` that actually ran."""
    return Path(root) / EXECUTIONS_SUBDIR / _check_id(unit_id, "unit_id")


def _publish_json(dest: Path, doc: dict[str, Any]) -> None:
    """tmp + fsync + os.replace.  On any failure the tmp is removed and ``dest`` is untouched."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = _json_bytes(doc)
    tmp = dest.with_name(f".{dest.name}.{os.getpid()}.{time.time_ns()}.tmp")
    fd = os.open(os.fspath(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, dest)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    try:
        _fsync_dir(dest.parent)
    except OSError:
        pass


def create_exclusive(path: Path | str, data: bytes) -> bool:
    """Honest claim primitive: create ``path`` with ``O_EXCL`` and write ``data``.

    Returns ``True`` when this caller created the file, ``False`` when another
    caller already had.  Any other ``OSError`` (ENOSPC, EROFS, ...) is raised
    after a partially written marker has been removed, so a failed claim never
    looks like a held one.
    """
    path = Path(path)
    try:
        fd = os.open(os.fspath(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return False
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    return True


def create_check_then_act(path: Path | str, data: bytes, race_window_s: float = 0.0) -> bool:
    """Mutation control: the TOCTOU version of :func:`create_exclusive`.

    ``exists()`` then (optionally) sleep, then a plain write.  Two racers both
    pass the check inside the window and both "win" - the double grant the
    TST-0157 detector must catch.  Never use outside a control experiment.
    """
    path = Path(path)
    if path.exists():
        return False
    if race_window_s > 0:
        time.sleep(float(race_window_s))
    path.write_bytes(data)
    return True


def _dispatch_result(
    status: str,
    unit_id: str,
    session_id: str,
    *,
    reason_code: str | None = None,
    winner_session_id: str | None = None,
    receipt: Path | None = None,
    record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "reason_code": reason_code,
        "unit_id": unit_id,
        "session_id": session_id,
        "winner_session_id": session_id if status == EXECUTED else winner_session_id,
        "receipt_path": str(receipt) if receipt is not None else None,
        "record": record,
    }


def dispatch(
    root: Path | str,
    unit_id: str,
    session_id: str,
    payload: Any = None,
    *,
    work: Any = None,
    atomic: bool = True,
    race_window_s: float = 0.0,
) -> dict[str, Any]:
    """Execute ``unit_id`` at most once across sessions; type every other caller.

    Returns ``{"status": EXECUTED, ...}`` for the one session that claimed the
    unit and published its receipt, and ``{"status": DUPLICATE-SUPPRESSED,
    "reason_code": ALREADY_EXECUTED | CLAIM_IN_PROGRESS, "winner_session_id":
    ...}`` for everyone else - including a serial second dispatch long after
    the first finished.  ``work(payload)`` (optional) is the unit body; its
    JSON-serialisable return value is stored in the receipt.  ``payload`` must
    be JSON-serialisable.

    Failures are loud: an ``OSError`` such as ENOSPC while claiming or
    publishing propagates to the caller, nothing is left claiming to have run,
    and the claim marker is removed so a retry can execute (make ``work``
    idempotent if it has side effects).  ``atomic=False`` selects the
    check-then-act mutant claim (control experiments only).
    """
    root = Path(root)
    unit_id = _check_id(unit_id, "unit_id")
    session_id = _check_id(session_id, "session_id")
    if work is not None and not callable(work):
        raise TypeError("work must be callable or None")
    prepare(root)
    receipt = receipt_path(root, unit_id)
    marker = claim_marker_path(root, unit_id)

    existing = _read_json(receipt)
    if existing is not None or receipt.exists():
        return _dispatch_result(
            DUPLICATE_SUPPRESSED,
            unit_id,
            session_id,
            reason_code=ALREADY_EXECUTED,
            winner_session_id=(existing or {}).get("session_id"),
            receipt=receipt,
        )

    claimed_at = time.time()
    marker_doc = {
        "unit_id": unit_id,
        "session_id": session_id,
        "claimed_at_unix": claimed_at,
        "atomic": bool(atomic),
    }
    if atomic:
        won = create_exclusive(marker, _json_bytes(marker_doc))
    else:
        won = create_check_then_act(marker, _json_bytes(marker_doc), race_window_s)
    if not won:
        holder = _read_json(marker) or {}
        return _dispatch_result(
            DUPLICATE_SUPPRESSED,
            unit_id,
            session_id,
            reason_code=ALREADY_EXECUTED if receipt.exists() else CLAIM_IN_PROGRESS,
            winner_session_id=holder.get("session_id"),
            receipt=receipt,
        )

    try:
        result = work(payload) if work is not None else None
        record: dict[str, Any] = {
            "schema": RECEIPT_SCHEMA,
            "status": EXECUTED,
            "unit_id": unit_id,
            "session_id": session_id,
            "payload": payload,
            "payload_sha256": _payload_digest(payload),
            "result": result,
            "claimed_at_unix": claimed_at,
            "executed_at_unix": time.time(),
            "atomic_claim": bool(atomic),
        }
        _publish_json(executions_dir(root, unit_id) / f"{session_id}.json", record)
        _publish_json(receipt, record)
    except BaseException:
        try:
            marker.unlink()
        except OSError:
            pass
        raise
    return _dispatch_result(EXECUTED, unit_id, session_id, receipt=receipt, record=record)


def count_receipts(root: Path | str, unit_id: str) -> int:
    """Receipt files published for ``unit_id`` (``<id>.json`` or any ``<id>.*.json`` variant)."""
    unit_id = _check_id(unit_id, "unit_id")
    directory = Path(root) / RECEIPTS_SUBDIR
    if not directory.is_dir():
        return 0
    return sum(
        1
        for p in directory.iterdir()
        if p.is_file()
        and p.suffix == ".json"
        and (p.name == f"{unit_id}.json" or p.name.startswith(f"{unit_id}."))
    )


def count_executions(root: Path | str, unit_id: str) -> int:
    """How many sessions actually executed ``unit_id`` (one record each)."""
    directory = executions_dir(root, unit_id)
    if not directory.is_dir():
        return 0
    return sum(1 for p in directory.iterdir() if p.is_file() and p.suffix == ".json")


def inspect_unit(root: Path | str, unit_id: str) -> dict[str, Any]:
    """On-disk state of ``unit_id``: claim marker, receipt, execution count."""
    root = Path(root)
    receipt = _read_json(receipt_path(root, unit_id))
    marker = _read_json(claim_marker_path(root, unit_id))
    return {
        "unit_id": unit_id,
        "claimed": claim_marker_path(root, unit_id).exists(),
        "claimed_by": (marker or {}).get("session_id"),
        "executed": receipt is not None,
        "executed_by": (receipt or {}).get("session_id"),
        "receipts": count_receipts(root, unit_id),
        "executions": count_executions(root, unit_id),
    }


def concurrent_pair(
    root: Path | str,
    unit_a: str,
    unit_b: str,
    session_a: str,
    session_b: str,
    *,
    skew_a: float = 0.0,
    skew_b: float = 0.0,
    atomic: bool = True,
    race_window_s: float = 0.0,
    payload: Any = None,
) -> list[dict[str, Any]]:
    """Two sessions dispatch concurrently (barrier start, per-side start skew).

    Returns ``[result_a, result_b]`` in argument order.  Same ``unit_a`` /
    ``unit_b`` is the contested case; different ids are the control.  An
    exception in either dispatch is re-raised here (silence is failure).
    """
    root = Path(root)
    prepare(root)
    barrier = threading.Barrier(2)
    results: list[dict[str, Any] | None] = [None, None]
    errors: list[BaseException | None] = [None, None]

    def run(slot: int, unit_id: str, session_id: str, skew: float) -> None:
        try:
            barrier.wait(timeout=30)
            if skew > 0:
                time.sleep(float(skew))
            results[slot] = dispatch(
                root,
                unit_id,
                session_id,
                payload,
                atomic=atomic,
                race_window_s=race_window_s,
            )
        except BaseException as exc:  # noqa: BLE001 - re-raised on the caller's thread
            errors[slot] = exc

    threads = [
        threading.Thread(target=run, args=(0, unit_a, session_a, skew_a), daemon=True),
        threading.Thread(target=run, args=(1, unit_b, session_b, skew_b), daemon=True),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    for slot, exc in enumerate(errors):
        if exc is not None:
            raise exc
    if any(t.is_alive() for t in threads) or any(r is None for r in results):
        raise RuntimeError(f"concurrent_pair: a dispatch did not finish ({unit_a!r}, {unit_b!r})")
    return [results[0], results[1]]  # type: ignore[list-item]


def contested_ok(results: list[dict[str, Any]], root: Path | str, unit_id: str) -> dict[str, Any]:
    """Judge a contested pair: exactly one EXECUTED, one DUPLICATE-SUPPRESSED, one receipt, one execution.

    The receipt on disk must name the session that reported EXECUTED, and every
    status must be one of the two typed outcomes.
    """
    statuses = [r.get("status") for r in results]
    executed = [r for r in results if r.get("status") == EXECUTED]
    suppressed = [r for r in results if r.get("status") == DUPLICATE_SUPPRESSED]
    untyped = [s for s in statuses if s not in (EXECUTED, DUPLICATE_SUPPRESSED)]
    receipts = count_receipts(root, unit_id)
    executions = count_executions(root, unit_id)
    receipt_doc = _read_json(receipt_path(root, unit_id)) or {}
    winner = executed[0].get("session_id") if len(executed) == 1 else None
    receipt_matches = winner is not None and receipt_doc.get("session_id") == winner
    ok = (
        len(results) == 2
        and len(executed) == 1
        and len(suppressed) == 1
        and not untyped
        and receipts == 1
        and executions == 1
        and receipt_matches
    )
    return {
        "ok": bool(ok),
        "unit_id": unit_id,
        "statuses": statuses,
        "executed": len(executed),
        "suppressed": len(suppressed),
        "untyped": untyped,
        "receipts": receipts,
        "executions": executions,
        "winner_session_id": winner,
        "receipt_names_winner": bool(receipt_matches),
        "loser_reason_code": suppressed[0].get("reason_code") if len(suppressed) == 1 else None,
    }


def distinct_ok(
    results: list[dict[str, Any]],
    root: Path | str,
    unit_a: str,
    unit_b: str,
) -> dict[str, Any]:
    """Judge the control pair: two different ids both EXECUTED, one receipt and one execution each."""
    statuses = [r.get("status") for r in results]
    receipts = {unit_a: count_receipts(root, unit_a), unit_b: count_receipts(root, unit_b)}
    executions = {
        unit_a: count_executions(root, unit_a),
        unit_b: count_executions(root, unit_b),
    }
    ids_match = len(results) == 2 and [r.get("unit_id") for r in results] == [unit_a, unit_b]
    ok = (
        unit_a != unit_b
        and ids_match
        and all(s == EXECUTED for s in statuses)
        and all(n == 1 for n in receipts.values())
        and all(n == 1 for n in executions.values())
    )
    return {
        "ok": bool(ok),
        "unit_ids": [unit_a, unit_b],
        "statuses": statuses,
        "receipts": receipts,
        "executions": executions,
        "ids_in_order": bool(ids_match),
    }
