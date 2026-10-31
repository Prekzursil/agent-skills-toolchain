"""Reconcile CRCP durable spool records with conversation checkpoints.

The module is deliberately independent of the delivery transport.  Recovery
operations only change durable local state; the normal delivery worker remains
responsible for publishing records whose state is ``spooled``.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ACTIVE_STATES = {"observed", "spooled", "publishing"}
TERMINAL_STATES = {"acked", "dead_letter", "dead-letter", "purged"}
INTERNAL_JSON_NAMES = {".publish_state.json", ".ingest_state.json"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except (ValueError, OverflowError):
            return None
    return None


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Durably replace one JSON file without exposing a partial document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        try:
            dir_fd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except (OSError, AttributeError):
            pass  # Directory fsync is not available on every Windows filesystem.
    except BaseException:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def _nested(record: dict[str, Any], key: str) -> Any:
    """Find a lifecycle identifier in common spool/envelope layouts."""
    candidates: list[dict[str, Any]] = [record]
    for candidate in candidates:
        for container in ("envelope", "checkpoint", "delivery", "meta", "poll"):
            value = candidate.get(container)
            if isinstance(value, dict) and value not in candidates:
                candidates.append(value)
    aliases = {
        "conversation_id": ("conversation_id", "conversation", "thread_id"),
        "update_time": ("update_time", "detected_update_time", "observed_update_time"),
        "event_key": ("event_key",),
        "envelope_id": ("envelope_id", "id"),
        "payload_sha256": ("payload_sha256", "sha256"),
    }
    for candidate in candidates:
        for alias in aliases.get(key, (key,)):
            value = candidate.get(alias)
            if value not in (None, ""):
                return value
    return None


def _identity(record: dict[str, Any]) -> dict[str, Any]:
    return {
        name: _nested(record, name)
        for name in (
            "event_key",
            "envelope_id",
            "conversation_id",
            "update_time",
            "payload_sha256",
        )
    }


def _state(record: dict[str, Any]) -> str:
    delivery = record.get("delivery")
    value = record.get("state") or record.get("status")
    if value is None and isinstance(delivery, dict):
        value = delivery.get("state") or delivery.get("status")
    return str(value or "spooled").lower()


def _state_time(record: dict[str, Any], path: Path) -> float:
    delivery = record.get("delivery")
    values = [
        record.get("publishing_at"),
        record.get("publish_started_at"),
        record.get("state_changed_at"),
        record.get("updated_at"),
        record.get("spooled_at"),
    ]
    if isinstance(delivery, dict):
        values[0:0] = [
            delivery.get("publishing_at"),
            delivery.get("started_at"),
            delivery.get("updated_at"),
        ]
    for value in values:
        parsed = _timestamp(value)
        if parsed is not None:
            return parsed
    return path.stat().st_mtime


def _iter_records(spool_dir: Path) -> Iterable[tuple[Path, dict[str, Any]]]:
    if not spool_dir.is_dir():
        return
    paths = list(spool_dir.glob("*.json"))
    pending = spool_dir / "pending"
    if pending.is_dir():
        paths.extend(pending.glob("*.json"))
    for path in sorted(paths):
        if (
            path.name in INTERNAL_JSON_NAMES
            or path.name.startswith(".")
            or path.is_symlink()
        ):
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            yield path, value


def _checkpoint_entries(data: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if isinstance(data, list):
        entries.extend(item for item in data if isinstance(item, dict))
    elif isinstance(data, dict):
        conversations = data.get("conversations")
        if isinstance(conversations, dict):
            for conversation_id, value in conversations.items():
                item = (
                    dict(value) if isinstance(value, dict) else {"update_time": value}
                )
                item.setdefault("conversation_id", conversation_id)
                entries.append(item)
        for key in ("events", "checkpoints", "published", "acked"):
            value = data.get(key)
            if isinstance(value, dict):
                for identity, details in value.items():
                    item = dict(details) if isinstance(details, dict) else {}
                    item.setdefault("event_key", identity)
                    entries.append(item)
            elif isinstance(value, list):
                entries.extend(item for item in value if isinstance(item, dict))
    return entries


def _load_checkpoints(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.is_file():
        return [], [f"checkpoint_missing:{path}"]
    try:
        if path.suffix.lower() == ".jsonl":
            data = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
        return _checkpoint_entries(data), []
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [], [f"checkpoint_unreadable:{type(exc).__name__}"]


def _is_checkpointed(
    record: dict[str, Any], checkpoint_ids: set[tuple[str, str]]
) -> bool:
    identity = _identity(record)
    for key in ("event_key", "envelope_id", "payload_sha256"):
        value = identity.get(key)
        if value is not None and (key, str(value)) in checkpoint_ids:
            return True
    cid = identity.get("conversation_id")
    update = identity.get("update_time")
    return (
        cid is not None
        and update is not None
        and ("conversation_update", f"{cid}\0{update}") in checkpoint_ids
    )


def scan_spool(
    spool_dir: Path,
    checkpoint_path: Path,
    *,
    stuck_after_seconds: float = 600.0,
    now: float | None = None,
) -> dict[str, Any]:
    """List active spool records missing checkpoints and stale publishes."""
    spool_dir = Path(spool_dir)
    checkpoint_path = Path(checkpoint_path)
    clock = datetime.now(timezone.utc).timestamp() if now is None else float(now)
    checkpoints, warnings = _load_checkpoints(checkpoint_path)
    checkpoint_ids: set[tuple[str, str]] = set()
    for item in checkpoints:
        identity = _identity(item)
        for key in ("event_key", "envelope_id", "payload_sha256"):
            if identity.get(key) is not None:
                checkpoint_ids.add((key, str(identity[key])))
        if (
            identity.get("conversation_id") is not None
            and identity.get("update_time") is not None
        ):
            checkpoint_ids.add(
                (
                    "conversation_update",
                    f"{identity['conversation_id']}\0{identity['update_time']}",
                )
            )

    orphans: list[dict[str, Any]] = []
    stuck: list[dict[str, Any]] = []
    malformed: list[dict[str, str]] = []
    total = 0
    if spool_dir.is_dir():
        candidate_paths = list(spool_dir.glob("*.json"))
        if (spool_dir / "pending").is_dir():
            candidate_paths.extend((spool_dir / "pending").glob("*.json"))
        candidate_paths = [
            p
            for p in sorted(candidate_paths)
            if p.name not in INTERNAL_JSON_NAMES and not p.name.startswith(".")
        ]
    else:
        candidate_paths = []
        warnings.append(f"spool_missing:{spool_dir}")
    loaded_paths: set[Path] = set()
    database_rows: dict[str, dict[str, Any]] = {}
    database_path = spool_dir / "delivery.sqlite3"
    if database_path.is_file():
        try:
            connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            try:
                rows = connection.execute("SELECT * FROM deliveries").fetchall()
                database_rows = {
                    str(Path(row["spool_path"]).resolve()): dict(row) for row in rows
                }
            finally:
                connection.close()
        except sqlite3.Error as exc:
            warnings.append(f"delivery_database_unreadable:{type(exc).__name__}")

    seen_database_paths: set[str] = set()
    state_map = {
        "pending": "spooled",
        "leased": "publishing",
        "delivered": "acked",
        "dead": "dead_letter",
    }
    for path, record in _iter_records(spool_dir):
        loaded_paths.add(path)
        total += 1
        row = database_rows.get(str(path.resolve()))
        if row:
            seen_database_paths.add(str(path.resolve()))
        state = state_map.get(str(row.get("status"))) if row else None
        state = state or _state(record)
        summary = {"path": str(path), "state": state, **_identity(record)}
        if row:
            summary.update(
                {
                    "attempts": row.get("attempts"),
                    "lease_owner_present": bool(row.get("lease_owner")),
                    "lease_until": row.get("lease_until"),
                    "last_error": row.get("last_error"),
                }
            )
        elif database_rows:
            summary["orphan_type"] = "spool_file_missing_delivery_record"
        if (state in ACTIVE_STATES or state == "acked") and not _is_checkpointed(
            record, checkpoint_ids
        ):
            orphans.append(summary)
        if state == "publishing":
            lease_until = row.get("lease_until") if row else None
            if isinstance(lease_until, (int, float)):
                age = max(0.0, clock - float(lease_until))
                stale = float(lease_until) <= clock
            else:
                age = max(0.0, clock - _state_time(record, path))
                stale = age >= stuck_after_seconds
            if stale and (age >= stuck_after_seconds or row is not None):
                stuck.append({**summary, "publishing_age_seconds": round(age, 3)})
    for resolved, row in database_rows.items():
        if resolved not in seen_database_paths and row.get("status") in (
            "pending",
            "leased",
        ):
            orphans.append(
                {
                    "path": row.get("spool_path"),
                    "state": state_map.get(
                        str(row.get("status")), str(row.get("status"))
                    ),
                    "envelope_id": row.get("envelope_id"),
                    "orphan_type": "delivery_record_missing_spool_file",
                    "attempts": row.get("attempts"),
                }
            )
    for path in candidate_paths:
        if path not in loaded_paths:
            malformed.append({"path": str(path), "error": "not_a_readable_json_object"})

    return {
        "scanned_at": utc_now(),
        "spool_dir": str(spool_dir),
        "checkpoint_path": str(checkpoint_path),
        "delivery_database": str(database_path) if database_path.is_file() else None,
        "stuck_after_seconds": stuck_after_seconds,
        "counts": {
            "spool_records": total,
            "checkpoint_records": len(checkpoints),
            "orphans": len(orphans),
            "stuck_publishing": len(stuck),
            "malformed": len(malformed),
        },
        "orphans": orphans,
        "stuck_publishing": stuck,
        "malformed": malformed,
        "warnings": warnings,
    }


def requeue_spooled(path: Path, *, reason: str = "manual_reconcile") -> dict[str, Any]:
    """Reset one non-terminal spool record for delivery-worker retry."""
    path = Path(path)
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError("spool record must be a JSON object")
    previous = _state(record)
    database_path = (
        path.parent.parent / "delivery.sqlite3"
        if path.parent.name == "pending"
        else path.parent / "delivery.sqlite3"
    )
    identity = _identity(record)
    if database_path.is_file():
        with sqlite3.connect(str(database_path), timeout=30.0) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM deliveries WHERE spool_path = ? OR envelope_id = ? LIMIT 1",
                (str(path), identity.get("envelope_id")),
            ).fetchone()
            if row is not None:
                previous = {
                    "pending": "spooled",
                    "leased": "publishing",
                    "delivered": "acked",
                    "dead": "dead_letter",
                }.get(row["status"], row["status"])
                if row["status"] not in ("pending", "leased"):
                    raise ValueError(
                        f"cannot requeue terminal delivery state: {previous}"
                    )
                now_epoch = datetime.now(timezone.utc).timestamp()
                connection.execute(
                    """UPDATE deliveries SET status='pending', next_attempt_at=?,
                       lease_owner=NULL, lease_until=NULL WHERE envelope_id=?""",
                    (now_epoch, row["envelope_id"]),
                )
                return {
                    "ok": True,
                    "path": str(path),
                    "previous_state": previous,
                    "state": "spooled",
                    **identity,
                }
    if previous in TERMINAL_STATES:
        raise ValueError(f"cannot requeue terminal spool state: {previous}")
    at = utc_now()
    history = record.setdefault("history", [])
    if not isinstance(history, list):
        history = record["history"] = []
    history.append({"from": previous, "to": "spooled", "at": at, "reason": reason})
    record["state"] = "spooled"
    record["state_changed_at"] = at
    record["requeued_at"] = at
    record["requeue_reason"] = reason
    for key in (
        "publishing_at",
        "publish_started_at",
        "lease_owner",
        "lease_expires_at",
        "next_attempt_at",
    ):
        record.pop(key, None)
    _atomic_write_json(path, record)
    return {
        "ok": True,
        "path": str(path),
        "previous_state": previous,
        "state": "spooled",
        **_identity(record),
    }


def mark_dead_letter(
    path: Path, dead_letter_dir: Path, *, reason: str
) -> dict[str, Any]:
    """Mark and atomically move one spool record into the dead-letter directory."""
    if not reason.strip():
        raise ValueError("dead-letter reason is required")
    path = Path(path)
    dead_letter_dir = Path(dead_letter_dir)
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError("spool record must be a JSON object")
    previous = _state(record)
    database_path = (
        path.parent.parent / "delivery.sqlite3"
        if path.parent.name == "pending"
        else path.parent / "delivery.sqlite3"
    )
    identity = _identity(record)
    if database_path.is_file():
        dead_letter_dir.mkdir(parents=True, exist_ok=True)
        destination = dead_letter_dir / path.name
        if destination.exists() and destination.resolve() != path.resolve():
            raise FileExistsError(f"dead-letter destination exists: {destination}")
        with sqlite3.connect(str(database_path), timeout=30.0) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM deliveries WHERE spool_path = ? OR envelope_id = ? LIMIT 1",
                (str(path), identity.get("envelope_id")),
            ).fetchone()
            if row is None:
                raise ValueError("spool record is missing from the delivery database")
            if row["status"] == "delivered":
                raise ValueError("cannot dead-letter an acknowledged delivery")
            os.replace(path, destination)
            now_epoch = datetime.now(timezone.utc).timestamp()
            connection.execute(
                """UPDATE deliveries SET status='dead', lease_owner=NULL,
                   lease_until=NULL, last_error=?, dead_at=? WHERE envelope_id=?""",
                (reason, now_epoch, row["envelope_id"]),
            )
        previous_state = {
            "pending": "spooled",
            "leased": "publishing",
            "dead": "dead_letter",
        }.get(row["status"], row["status"])
        return {
            "ok": True,
            "path": str(destination),
            "previous_state": previous_state,
            "state": "dead_letter",
            **identity,
        }
    at = utc_now()
    history = record.setdefault("history", [])
    if not isinstance(history, list):
        history = record["history"] = []
    history.append({"from": previous, "to": "dead_letter", "at": at, "reason": reason})
    record.update(
        {
            "state": "dead_letter",
            "state_changed_at": at,
            "dead_lettered_at": at,
            "dead_letter_reason": reason,
        }
    )
    dead_letter_dir.mkdir(parents=True, exist_ok=True)
    destination = dead_letter_dir / path.name
    if destination.exists() and destination.resolve() != path.resolve():
        raise FileExistsError(f"dead-letter destination exists: {destination}")
    _atomic_write_json(path, record)
    if destination.resolve() != path.resolve():
        os.replace(path, destination)
    return {
        "ok": True,
        "path": str(destination),
        "previous_state": previous,
        "state": "dead_letter",
        **_identity(record),
    }


def _default_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconcile CRCP spool and conversation checkpoints"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="report orphaned and stuck spool records")
    scan.add_argument("--spool", type=Path, default=_default_root() / "spool")
    scan.add_argument(
        "--checkpoint",
        type=Path,
        default=_default_root() / "reports" / "live_bridge_state.json",
    )
    scan.add_argument("--stuck-after", type=float, default=600.0, metavar="SECONDS")
    requeue = sub.add_parser("requeue", help="reset a spool record to spooled")
    requeue.add_argument("record", type=Path)
    requeue.add_argument("--reason", default="manual_reconcile")
    dead = sub.add_parser(
        "dead-letter", help="move a spool record to dead-letter storage"
    )
    dead.add_argument("record", type=Path)
    dead.add_argument("--dir", type=Path, default=_default_root() / "dead-letter")
    dead.add_argument("--reason", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "scan":
            result = scan_spool(
                args.spool, args.checkpoint, stuck_after_seconds=args.stuck_after
            )
            code = (
                2 if result["warnings"] else (1 if result["counts"]["malformed"] else 0)
            )
        elif args.command == "requeue":
            result = requeue_spooled(args.record, reason=args.reason)
            code = 0
        else:
            result = mark_dead_letter(args.record, args.dir, reason=args.reason)
            code = 0
        print(json.dumps(result, indent=2, default=str))
        return code
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
