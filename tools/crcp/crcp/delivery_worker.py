"""Durable, bounded, at-least-once delivery worker for CRCP envelopes.

The spool contains JSON payloads while SQLite owns scheduling and claim state.
Multiple worker processes may share a spool: each delivery is protected by a
renewable-by-reclaim lease, and an expired lease is eligible for another try.
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable


Sender = Callable[..., dict[str, Any]]


class BacklogFullError(RuntimeError):
    """Raised before enqueue when accepting an item would exceed a cap."""


def _default_sender(envelope: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    try:
        from .bus import publish_envelope
    except ImportError:  # permits direct loading during deployment smoke tests
        from bus import publish_envelope
    return publish_envelope(envelope, **kwargs)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary_path), str(path))
        try:
            directory_fd = os.open(str(path.parent), os.O_RDONLY)
        except (AttributeError, OSError):
            return
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


class DeliveryWorker:
    """Persist envelopes and deliver them independently from their producers.

    ``sender`` must accept ``sender(envelope, **publish_options)``. By default it
    lazily calls :func:`crcp.bus.publish_envelope`, avoiding an import cycle.
    Backlog item and byte caps reject new work; accepted work is never evicted
    to make room. Items older than ``max_age_seconds`` are moved to dead-letter.
    """

    def __init__(
        self,
        spool_dir: Path,
        *,
        sender: Sender | None = None,
        max_attempts: int = 8,
        base_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 300.0,
        jitter_fraction: float = 0.25,
        lease_seconds: float = 60.0,
        max_items: int = 10_000,
        max_age_seconds: float = 7 * 24 * 60 * 60,
        max_total_bytes: int = 1024 * 1024 * 1024,
        owner_id: str | None = None,
        clock: Callable[[], float] = time.time,
        rng: random.Random | None = None,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if base_backoff_seconds < 0 or max_backoff_seconds < 0:
            raise ValueError("backoff values must be non-negative")
        if not 0 <= jitter_fraction <= 1:
            raise ValueError("jitter_fraction must be between 0 and 1")
        if lease_seconds <= 0 or max_age_seconds <= 0:
            raise ValueError("lease and age limits must be positive")
        if max_items < 1 or max_total_bytes < 1:
            raise ValueError("backlog caps must be positive")

        self.spool_dir = Path(spool_dir)
        self.pending_dir = self.spool_dir / "pending"
        self.dead_letter_dir = self.spool_dir / "dead-letter"
        self.database_path = self.spool_dir / "delivery.sqlite3"
        self.sender = sender or _default_sender
        self.max_attempts = max_attempts
        self.base_backoff_seconds = base_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.jitter_fraction = jitter_fraction
        self.lease_seconds = lease_seconds
        self.max_items = max_items
        self.max_age_seconds = max_age_seconds
        self.max_total_bytes = max_total_bytes
        self.owner_id = owner_id or f"{os.getpid()}-{uuid.uuid4().hex}"
        self._clock = clock
        self._rng = rng or random.Random()
        self._thread_lock = threading.Lock()

        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.dead_letter_dir.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS deliveries (
                    envelope_id TEXT PRIMARY KEY,
                    spool_path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('pending', 'leased', 'delivered', 'dead')
                    ),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at REAL NOT NULL,
                    lease_owner TEXT,
                    lease_until REAL,
                    last_error TEXT,
                    delivered_at REAL,
                    dead_at REAL
                );
                CREATE INDEX IF NOT EXISTS deliveries_ready
                    ON deliveries(status, next_attempt_at, created_at);
                """
            )

    @staticmethod
    def _envelope_id(envelope: dict[str, Any], encoded: bytes) -> str:
        supplied = envelope.get("id")
        if supplied is not None and str(supplied).strip():
            return str(supplied)
        import hashlib

        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _file_name(envelope_id: str) -> str:
        import hashlib

        digest = hashlib.sha256(envelope_id.encode("utf-8")).hexdigest()
        return f"envelope_{digest}.json"

    def enqueue(
        self,
        envelope: dict[str, Any],
        *,
        project: str | None = None,
        to_agents: list[str] | None = None,
        url: str | None = None,
    ) -> dict[str, Any]:
        """Durably accept an envelope, or return its existing queue state.

        Capacity checks and insertion are serialized across processes by an
        immediate SQLite transaction. The payload is fsynced before commit.
        """
        if not isinstance(envelope, dict):
            raise TypeError("envelope must be a dictionary")
        canonical = json.dumps(
            envelope, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
        envelope_id = self._envelope_id(envelope, canonical)
        options: dict[str, Any] = {}
        if project is not None:
            options["project"] = project
        if to_agents is not None:
            options["to_agents"] = list(to_agents)
        if url is not None:
            options["url"] = url
        record = {"envelope": envelope, "publish_options": options}
        payload = json.dumps(record, indent=2, default=str).encode("utf-8")
        size_bytes = len(payload)
        path = self.pending_dir / self._file_name(envelope_id)
        now = self._clock()

        with self._thread_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT status, attempts FROM deliveries WHERE envelope_id = ?",
                (envelope_id,),
            ).fetchone()
            if existing is not None:
                return {
                    "ok": True,
                    "queued": existing["status"] in ("pending", "leased"),
                    "duplicate": True,
                    "envelope_id": envelope_id,
                    "status": existing["status"],
                    "attempts": existing["attempts"],
                }

            self._expire_old_locked(connection, now)
            totals = connection.execute(
                """
                SELECT COUNT(*) AS item_count, COALESCE(SUM(size_bytes), 0) AS bytes
                FROM deliveries WHERE status IN ('pending', 'leased')
                """
            ).fetchone()
            if totals["item_count"] + 1 > self.max_items:
                raise BacklogFullError("delivery backlog item cap reached")
            if totals["bytes"] + size_bytes > self.max_total_bytes:
                raise BacklogFullError("delivery backlog byte cap reached")

            _atomic_write(path, payload)
            connection.execute(
                """
                INSERT INTO deliveries (
                    envelope_id, spool_path, size_bytes, created_at, status,
                    attempts, next_attempt_at
                ) VALUES (?, ?, ?, ?, 'pending', 0, ?)
                """,
                (envelope_id, str(path), size_bytes, now, now),
            )
        return {
            "ok": True,
            "queued": True,
            "duplicate": False,
            "envelope_id": envelope_id,
            "status": "pending",
        }

    def _expire_old_locked(self, connection: sqlite3.Connection, now: float) -> int:
        cutoff = now - self.max_age_seconds
        rows = connection.execute(
            """
            SELECT * FROM deliveries
            WHERE status IN ('pending', 'leased') AND created_at <= ?
              AND (status != 'leased' OR lease_until IS NULL OR lease_until <= ?)
            ORDER BY created_at
            """,
            (cutoff, now),
        ).fetchall()
        for row in rows:
            self._move_to_dead_letter_locked(connection, row, now, "max_age_exceeded")
        return len(rows)

    def expire_old(self) -> int:
        """Move over-age, non-actively-leased items to dead-letter."""
        now = self._clock()
        with self._thread_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            return self._expire_old_locked(connection, now)

    def _move_to_dead_letter_locked(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        now: float,
        reason: str,
    ) -> Path:
        source = Path(row["spool_path"])
        destination = self.dead_letter_dir / source.name
        try:
            os.replace(str(source), str(destination))
        except FileNotFoundError:
            pass
        connection.execute(
            """
            UPDATE deliveries
            SET status = 'dead', lease_owner = NULL, lease_until = NULL,
                last_error = ?, dead_at = ?
            WHERE envelope_id = ?
            """,
            (reason, now, row["envelope_id"]),
        )
        return destination

    def _claim(self) -> sqlite3.Row | None:
        now = self._clock()
        with self._thread_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._expire_old_locked(connection, now)
            row = connection.execute(
                """
                SELECT * FROM deliveries
                WHERE (
                    status = 'pending'
                    OR (status = 'leased' AND lease_until <= ?)
                ) AND next_attempt_at <= ?
                ORDER BY next_attempt_at, created_at
                LIMIT 1
                """,
                (now, now),
            ).fetchone()
            if row is None:
                return None
            changed = connection.execute(
                """
                UPDATE deliveries
                SET status = 'leased', lease_owner = ?, lease_until = ?
                WHERE envelope_id = ? AND (
                    status = 'pending'
                    OR (status = 'leased' AND lease_until <= ?)
                )
                """,
                (
                    self.owner_id,
                    now + self.lease_seconds,
                    row["envelope_id"],
                    now,
                ),
            ).rowcount
            if changed != 1:
                return None
            return connection.execute(
                "SELECT * FROM deliveries WHERE envelope_id = ?",
                (row["envelope_id"],),
            ).fetchone()

    def _backoff(self, failures: int) -> float:
        exponent = min(failures - 1, 62)
        base = min(
            self.max_backoff_seconds,
            self.base_backoff_seconds * (2**exponent),
        )
        spread = base * self.jitter_fraction
        return max(0.0, base + self._rng.uniform(-spread, spread))

    def _acknowledge(self, envelope_id: str) -> bool:
        now = self._clock()
        spool_path: str | None = None
        with self._thread_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT spool_path FROM deliveries WHERE envelope_id = ?",
                (envelope_id,),
            ).fetchone()
            changed = connection.execute(
                """
                UPDATE deliveries
                SET status = 'delivered', delivered_at = ?, lease_owner = NULL,
                    lease_until = NULL, last_error = NULL
                WHERE envelope_id = ? AND status = 'leased' AND lease_owner = ?
                """,
                (now, envelope_id, self.owner_id),
            ).rowcount
            if changed == 1 and row is not None:
                spool_path = row["spool_path"]
        if spool_path:
            try:
                Path(spool_path).unlink()
            except FileNotFoundError:
                pass
        return changed == 1

    def _fail(self, row: sqlite3.Row, error: BaseException) -> dict[str, Any]:
        now = self._clock()
        failures = int(row["attempts"]) + 1
        error_name = type(error).__name__[:120]
        with self._thread_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                """
                SELECT * FROM deliveries
                WHERE envelope_id = ? AND status = 'leased' AND lease_owner = ?
                """,
                (row["envelope_id"], self.owner_id),
            ).fetchone()
            if current is None:
                return {"ok": False, "status": "lease_lost"}
            if failures >= self.max_attempts:
                connection.execute(
                    "UPDATE deliveries SET attempts = ? WHERE envelope_id = ?",
                    (failures, row["envelope_id"]),
                )
                destination = self._move_to_dead_letter_locked(
                    connection, current, now, error_name
                )
                return {
                    "ok": False,
                    "status": "dead",
                    "attempts": failures,
                    "dead_letter": str(destination),
                    "error": error_name,
                }
            delay = self._backoff(failures)
            connection.execute(
                """
                UPDATE deliveries
                SET status = 'pending', attempts = ?, next_attempt_at = ?,
                    lease_owner = NULL, lease_until = NULL, last_error = ?
                WHERE envelope_id = ? AND lease_owner = ?
                """,
                (
                    failures,
                    now + delay,
                    error_name,
                    row["envelope_id"],
                    self.owner_id,
                ),
            )
        return {
            "ok": False,
            "status": "retry",
            "attempts": failures,
            "retry_in_seconds": delay,
            "error": error_name,
        }

    def deliver_one(self) -> dict[str, Any] | None:
        """Claim and attempt one ready item; return ``None`` when idle."""
        row = self._claim()
        if row is None:
            return None
        envelope_id = row["envelope_id"]
        try:
            record = json.loads(Path(row["spool_path"]).read_text(encoding="utf-8"))
            envelope = record["envelope"]
            options = record.get("publish_options") or {}
            send_result = self.sender(envelope, **options)
            if isinstance(send_result, dict) and send_result.get("ok") is False:
                raise RuntimeError("sender_returned_not_ok")
        except Exception as error:
            result = self._fail(row, error)
            result["envelope_id"] = envelope_id
            return result
        acknowledged = self._acknowledge(envelope_id)
        return {
            "ok": acknowledged,
            "status": "delivered" if acknowledged else "lease_lost",
            "envelope_id": envelope_id,
        }

    def process_once(self, *, limit: int = 20) -> dict[str, Any]:
        """Attempt up to ``limit`` ready deliveries without waiting."""
        if limit < 1:
            raise ValueError("limit must be at least 1")
        results: list[dict[str, Any]] = []
        for _ in range(limit):
            result = self.deliver_one()
            if result is None:
                break
            results.append(result)
        return {"processed": len(results), "results": results, "stats": self.stats()}

    def run_forever(
        self,
        stop_event: threading.Event,
        *,
        poll_interval_seconds: float = 1.0,
        batch_size: int = 20,
    ) -> None:
        """Run until ``stop_event`` is set, sleeping interruptibly when idle."""
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        while not stop_event.is_set():
            outcome = self.process_once(limit=batch_size)
            if outcome["processed"] == 0:
                stop_event.wait(poll_interval_seconds)

    def stats(self) -> dict[str, Any]:
        """Return queue counts, bytes, and age without exposing payloads."""
        now = self._clock()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS item_count,
                       COALESCE(SUM(size_bytes), 0) AS bytes,
                       MIN(created_at) AS oldest
                FROM deliveries GROUP BY status
                """
            ).fetchall()
        by_status = {
            row["status"]: {"items": row["item_count"], "bytes": row["bytes"]}
            for row in rows
        }
        active = [row for row in rows if row["status"] in ("pending", "leased")]
        oldest = min(
            (row["oldest"] for row in active if row["oldest"] is not None),
            default=None,
        )
        return {
            "by_status": by_status,
            "backlog_items": sum(row["item_count"] for row in active),
            "backlog_bytes": sum(row["bytes"] for row in active),
            "oldest_backlog_age_seconds": max(0.0, now - oldest)
            if oldest is not None
            else 0.0,
        }
