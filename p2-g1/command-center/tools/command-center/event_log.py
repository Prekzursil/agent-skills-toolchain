"""Append-only JSONL event writer safe under concurrent O_APPEND writers.

Production path: one os.write of a complete UTF-8 JSON line plus LF on an
O_APPEND fd. No POSIX fcntl. On Windows O_APPEND is FILE_APPEND_DATA.

The chunked mutant (MUTANT_CHUNK-byte writes of the same line) is only for
the IMP-0429 / ADV-0116 negative control; it is not a production mode.
"""
from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

MUTANT_CHUNK = 7
GENESIS_HASH = "0" * 64
PAD = "x" * 128
_LOCK_POLL = 0.0005


def uses_fcntl() -> bool:
    return False


def encode_line(record: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(record), ensure_ascii=True, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _open_append(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if getattr(os, "O_BINARY", 0):
        flags |= os.O_BINARY
    return os.open(path, flags, 0o644)


def _write_atomic(fd: int, data: bytes) -> None:
    """Single write() of one complete JSONL record (production)."""
    wrote = os.write(fd, data)
    if wrote != len(data):
        raise OSError(f"short O_APPEND write: {wrote} of {len(data)}")


def _write_chunked(fd: int, data: bytes, chunk: int = MUTANT_CHUNK) -> None:
    """Mutation: several write()s of one record so concurrent appends tear."""
    view = memoryview(data)
    offset = 0
    n = len(data)
    while offset < n:
        wrote = os.write(fd, view[offset : offset + chunk])
        if wrote <= 0:
            raise OSError("chunked O_APPEND write returned 0")
        offset += wrote


class EventLog:
    """Keep a long-lived O_APPEND fd. fsync is not on the production path."""

    def __init__(self, path: Path | str, atomic: bool = True) -> None:
        self.path = Path(path)
        self.atomic = atomic
        self._fd: int | None = None

    def open(self) -> None:
        if self._fd is None:
            self._fd = _open_append(self.path)

    def close(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def append(self, record: Mapping[str, Any]) -> None:
        if self._fd is None:
            self.open()
        assert self._fd is not None
        data = encode_line(record)
        if self.atomic:
            _write_atomic(self._fd, data)
        else:
            _write_chunked(self._fd, data)

    def __enter__(self) -> EventLog:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _parse_lines(raw: bytes) -> tuple[list[str], bool, int]:
    if not raw:
        return [], False, 0
    torn_tail = not raw.endswith(b"\n")
    text = raw.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    torn_bytes = 0
    if torn_tail and lines:
        torn_bytes = len(lines[-1].encode("utf-8", errors="replace"))
    return lines, torn_tail, torn_bytes


def scan(path: Path | str, expected: int | None = None) -> dict[str, Any]:
    p = Path(path)
    raw = p.read_bytes() if p.is_file() else b""
    lines, torn_tail, _torn_bytes = _parse_lines(raw)
    parsed = 0
    torn = 0
    torn_samples: list[dict[str, Any]] = []
    pairs: set[tuple[Any, Any]] = set()
    for idx, line in enumerate(lines):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            torn += 1
            if len(torn_samples) < 8:
                torn_samples.append(
                    {
                        "line_index": idx,
                        "bytes": len(line.encode("utf-8", errors="replace")),
                        "error": type(exc).__name__,
                        "head_hex": line.encode("utf-8", errors="replace")[:24].hex(),
                    }
                )
            continue
        if not isinstance(obj, dict):
            torn += 1
            continue
        parsed += 1
        if "writer_id" in obj and "seq" in obj:
            pairs.add((obj.get("writer_id"), obj.get("seq")))
    if torn_tail:
        torn += 1
    line_count = len(lines)
    exp = int(expected) if expected is not None else line_count
    unique = len(pairs)
    all_present = (
        line_count == exp and parsed == exp and torn == 0 and unique == exp
    )
    return {
        "all_present": all_present,
        "bytes": len(raw),
        "expected": exp,
        "interleaved_or_truncated": torn > 0 or not all_present,
        "line_count": line_count,
        "parsed": parsed,
        "torn": torn,
        "torn_samples": torn_samples,
        "unique_writer_seq": unique,
    }


def _fanout_worker(
    path_str: str,
    writer_id: int,
    per_writer: int,
    atomic: bool,
    ready: Any,
    errors: Any,
) -> None:
    fd = None
    try:
        ready.wait(30)
        fd = _open_append(Path(path_str))
        write = _write_atomic if atomic else _write_chunked
        for seq in range(per_writer):
            rec = {
                "kind": "imp0429-writer",
                "pad": PAD,
                "seq": seq,
                "writer_id": writer_id,
            }
            write(fd, encode_line(rec))
    except Exception as exc:  # noqa: BLE001 - worker must report, not raise
        errors.append(f"writer_{writer_id}:{type(exc).__name__}:{exc}")
    finally:
        if fd is not None:
            os.close(fd)


def run_fanout(
    path: Path | str,
    writers: int = 8,
    per_writer: int = 500,
    atomic: bool = True,
) -> dict[str, Any]:
    """8-process (default) fan-out append of `per_writer` events each."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    ctx = multiprocessing.get_context("fork" if os.name != "nt" else "spawn")
    ready = ctx.Event()
    errors = ctx.Manager().list()
    procs: list[Any] = []
    t0 = time.perf_counter()
    for wid in range(writers):
        proc = ctx.Process(
            target=_fanout_worker,
            args=(str(dest), wid, per_writer, atomic, ready, errors),
        )
        proc.start()
        procs.append(proc)
    ready.set()
    writer_failures: list[str] = []
    for proc in procs:
        proc.join(120)
        if proc.is_alive():
            proc.kill()
            proc.join(5)
            writer_failures.append("timeout")
        elif proc.exitcode not in (0, None):
            writer_failures.append(f"exit:{proc.exitcode}")
    writer_failures.extend(list(errors))
    wall = round(time.perf_counter() - t0, 4)
    result = scan(dest, expected=writers * per_writer)
    result.update(
        {
            "atomic": atomic,
            "mutant_chunk": None if atomic else MUTANT_CHUNK,
            "os_name": os.name,
            "per_writer": per_writer,
            "wall_seconds": wall,
            "writer_failures": writer_failures,
            "writers": writers,
        }
    )
    return result


def _lock_dir(path: Path) -> Path:
    return path.with_name(path.name + ".lock")


def _acquire_mkdir(path: Path, timeout: float = 30.0) -> Path:
    lock = _lock_dir(path)
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.mkdir(lock)
            return lock
        except FileExistsError:
            if time.monotonic() > deadline:
                raise TimeoutError(f"event-log mkdir lock timed out: {lock}")
            time.sleep(_LOCK_POLL)


def _release_mkdir(lock: Path) -> None:
    try:
        os.rmdir(lock)
    except FileNotFoundError:
        pass


def _hash_record(record: Mapping[str, Any]) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _tail_meta(path: Path) -> tuple[int, str]:
    if not path.is_file() or path.stat().st_size == 0:
        return 0, GENESIS_HASH
    raw = path.read_bytes()
    lines, torn_tail, _ = _parse_lines(raw)
    if torn_tail or not lines:
        return 0, GENESIS_HASH
    last = json.loads(lines[-1])
    seq = int(last.get("seq") or len(lines))
    prev = str(last.get("hash") or GENESIS_HASH)
    return seq, prev


def append_record(path: Path | str, record: Mapping[str, Any]) -> None:
    """Atomic O_APPEND of one JSON object. Adds hash-chain fields when absent."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lock = _acquire_mkdir(p)
    try:
        payload = dict(record)
        if "hash" not in payload:
            seq, prev = _tail_meta(p)
            payload.setdefault("seq", seq + 1)
            payload.setdefault("prev_hash", prev)
            payload["hash"] = _hash_record(payload)
        fd = _open_append(p)
        try:
            _write_atomic(fd, encode_line(payload))
        finally:
            os.close(fd)
    finally:
        _release_mkdir(lock)


@dataclass
class LogRead:
    ok: bool
    parsed: int
    intact_links: int
    torn_tail: bool = False
    torn_bytes: int = 0
    chain_break_at: int | None = None
    chain_break_name: str | None = None
    chain_break_reason: str | None = None
    errors: list[str] = field(default_factory=list)
    records: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RepairReport:
    records_lost: int
    intact_records: int
    torn_tail_before: bool


def read_log(path: Path | str) -> LogRead:
    p = Path(path)
    raw = p.read_bytes() if p.is_file() else b""
    lines, torn_tail, torn_bytes = _parse_lines(raw)
    errors: list[str] = []
    records: list[dict[str, Any]] = []
    parsed = 0
    for idx, line in enumerate(lines):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"json:{idx}:{exc}")
            if idx == len(lines) - 1:
                torn_tail = True
                torn_bytes = len(line.encode("utf-8", errors="replace"))
            result = LogRead(
                ok=False,
                parsed=parsed,
                intact_links=parsed,
                torn_tail=torn_tail,
                torn_bytes=torn_bytes,
                errors=errors,
                records=records,
            )
            return result
        if not isinstance(obj, dict):
            errors.append(f"not-object:{idx}")
            return LogRead(
                ok=False,
                parsed=parsed,
                intact_links=parsed,
                torn_tail=torn_tail,
                torn_bytes=torn_bytes,
                errors=errors,
                records=records,
            )
        parsed += 1
        records.append(obj)

    intact = 0
    prev = GENESIS_HASH
    break_at = None
    break_name = None
    break_reason = None
    for rec in records:
        seq = int(rec.get("seq") or (intact + 1))
        expected_prev = prev
        got_prev = str(rec.get("prev_hash") or "")
        got_hash = str(rec.get("hash") or "")
        want_hash = _hash_record(rec)
        if got_prev != expected_prev or got_hash != want_hash:
            break_at = seq
            break_name = f"seq={seq}"
            break_reason = (
                "hash-mismatch" if got_hash != want_hash else "prev-hash-mismatch"
            )
            errors.append(f"chain-break {break_name} {break_reason}")
            break
        intact += 1
        prev = got_hash

    ok = torn_tail is False and break_at is None and not errors
    return LogRead(
        ok=ok,
        parsed=parsed,
        intact_links=intact,
        torn_tail=torn_tail,
        torn_bytes=torn_bytes,
        chain_break_at=break_at,
        chain_break_name=break_name,
        chain_break_reason=break_reason,
        errors=errors,
        records=records,
    )


def repair(path: Path | str) -> RepairReport:
    p = Path(path)
    before = read_log(p)
    keep = before.records[: before.intact_links]
    raw = encode_line  # local alias
    blob = b"".join(raw(rec) for rec in keep)
    p.write_bytes(blob)
    lost = max(0, before.parsed - len(keep))
    if before.torn_tail:
        lost = max(lost, 1)
    return RepairReport(
        records_lost=lost,
        intact_records=len(keep),
        torn_tail_before=before.torn_tail,
    )


def replay(path: Path | str) -> list[dict[str, Any]]:
    result = read_log(path)
    return list(result.records[: result.intact_links] or result.records)


def _concurrent_worker(
    path_str: str, writer_id: int, each: int, ready: Any, errors: Any
) -> None:
    try:
        ready.wait(30)
        for i in range(each):
            append_record(
                path_str,
                {
                    "i": i,
                    "unit": "cc-event-log",
                    "verb": "append",
                    "writer_id": writer_id,
                },
            )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"writer_{writer_id}:{type(exc).__name__}:{exc}")


def run_concurrent(
    path: Path | str,
    writers: int = 8,
    each: int = 500,
    timeout: float = 160.0,
) -> dict[str, Any]:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    ctx = multiprocessing.get_context("fork" if os.name != "nt" else "spawn")
    ready = ctx.Event()
    errors = ctx.Manager().list()
    procs: list[Any] = []
    t0 = time.perf_counter()
    for wid in range(writers):
        proc = ctx.Process(
            target=_concurrent_worker,
            args=(str(dest), wid, each, ready, errors),
        )
        proc.start()
        procs.append(proc)
    ready.set()
    exit_codes: list[int] = []
    for proc in procs:
        proc.join(timeout)
        if proc.is_alive():
            proc.kill()
            proc.join(5)
            exit_codes.append(124)
        else:
            exit_codes.append(int(proc.exitcode or 0))
    wall = round(time.perf_counter() - t0, 4)
    log = read_log(dest)
    counts: dict[str, int] = {str(i): 0 for i in range(writers)}
    for rec in log.records:
        key = str(rec.get("writer_id"))
        if key in counts:
            counts[key] += 1
    err_list = list(errors)
    interleaved = max(0, log.parsed - log.intact_links) if not log.ok else 0
    return {
        "all_workers_ok": all(c == 0 for c in exit_codes) and not err_list,
        "chain_ok": log.ok and log.intact_links == writers * each,
        "parsed": log.parsed,
        "intact_links": log.intact_links,
        "interleaved_lines": interleaved,
        "torn_tail": log.torn_tail,
        "writer_counts": counts,
        "wall_seconds": wall,
        "exit_codes": exit_codes,
        "errors": err_list,
        "path": str(dest),
    }
