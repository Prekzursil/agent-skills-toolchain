"""Operator-safe dead-letter management for the CRCP durable spool."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # Package installation and direct script execution are both supported.
    from .reconcile import _atomic_write_json, _identity, _state, utc_now
except ImportError:
    from reconcile import _atomic_write_json, _identity, _state, utc_now


_SECRET_KEY_PARTS = (
    "authorization",
    "access_token",
    "refresh_token",
    "id_token",
    "proof_token",
    "prepare_token",
    "turnstile_token",
    "registration_token",
    "api_key",
    "secret",
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")


def _redact(value: Any, key: str = "") -> Any:
    lowered = key.lower().replace("-", "_")
    if any(part in lowered for part in _SECRET_KEY_PARTS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _JWT_RE.sub("[REDACTED_JWT]", _BEARER_RE.sub("Bearer [REDACTED]", value))
    return value


def _paths(dead_letter_dir: Path) -> list[Path]:
    if not dead_letter_dir.is_dir():
        return []
    return [
        path
        for path in sorted(
            dead_letter_dir.glob("*.json"), key=lambda p: (p.stat().st_mtime, p.name)
        )
        if not path.name.startswith(".") and not path.is_symlink()
    ]


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"dead-letter record is not a JSON object: {path.name}")
    return value


def _resolve(dead_letter_dir: Path, entry: str | Path) -> Path:
    """Resolve a filename or lifecycle identity without allowing path traversal."""
    dead_letter_dir = Path(dead_letter_dir)
    requested = Path(entry)
    if requested.name != str(entry) or requested.name in ("", ".", ".."):
        raise ValueError("entry must be a filename or event identity, not a path")
    direct = dead_letter_dir / requested.name
    if direct.is_file() and not direct.is_symlink():
        return direct
    matches: list[Path] = []
    for path in _paths(dead_letter_dir):
        try:
            identity = _identity(_read(path))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if str(entry) in {
            str(value) for value in identity.values() if value is not None
        }:
            matches.append(path)
    if not matches:
        raise FileNotFoundError(f"dead-letter entry not found: {entry}")
    if len(matches) > 1:
        raise ValueError(f"identity is ambiguous; use a filename: {entry}")
    return matches[0]


def list_dead_letters(dead_letter_dir: Path) -> dict[str, Any]:
    """Return metadata-only summaries; malformed entries remain visible."""
    dead_letter_dir = Path(dead_letter_dir)
    entries: list[dict[str, Any]] = []
    malformed = 0
    now = datetime.now(timezone.utc).timestamp()
    database_path = dead_letter_dir.parent / "delivery.sqlite3"
    database_rows: dict[str, dict[str, Any]] = {}
    if database_path.is_file():
        try:
            connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            try:
                database_rows = {
                    Path(row["spool_path"]).name: dict(row)
                    for row in connection.execute(
                        "SELECT * FROM deliveries WHERE status='dead'"
                    )
                }
            finally:
                connection.close()
        except sqlite3.Error:
            database_rows = {}
    for path in _paths(dead_letter_dir):
        try:
            record = _read(path)
            database_row = database_rows.get(path.name)
            timestamp = (
                (database_row or {}).get("dead_at")
                or record.get("dead_lettered_at")
                or record.get("state_changed_at")
            )
            try:
                parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                created = parsed.timestamp()
            except (ValueError, OverflowError):
                created = path.stat().st_mtime
            entries.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "age_seconds": round(max(0.0, now - created), 3),
                    "state": "dead_letter" if database_row else _state(record),
                    "reason": _redact(
                        (database_row or {}).get("last_error")
                        or record.get("dead_letter_reason"),
                        "dead_letter_reason",
                    ),
                    "attempts": (database_row or {}).get("attempts"),
                    **_identity(record),
                }
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            malformed += 1
            entries.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "malformed": True,
                    "error": type(exc).__name__,
                }
            )
    return {
        "dead_letter_dir": str(dead_letter_dir),
        "count": len(entries),
        "malformed": malformed,
        "entries": entries,
    }


def inspect_dead_letter(dead_letter_dir: Path, entry: str | Path) -> dict[str, Any]:
    """Read one entry, recursively redacting credential-shaped fields and strings."""
    path = _resolve(Path(dead_letter_dir), entry)
    result = {"name": path.name, "path": str(path), "record": _redact(_read(path))}
    database_path = Path(dead_letter_dir).parent / "delivery.sqlite3"
    if database_path.is_file():
        with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM deliveries WHERE status='dead' AND spool_path LIKE ? LIMIT 1",
                (f"%{path.name}",),
            ).fetchone()
            if row is not None:
                result["delivery"] = _redact(dict(row))
    return result


def requeue_dead_letter(
    dead_letter_dir: Path, entry: str | Path, spool_dir: Path
) -> dict[str, Any]:
    """Move one dead letter back to the spool in ``spooled`` state."""
    source = _resolve(Path(dead_letter_dir), entry)
    spool_dir = Path(spool_dir)
    record = _read(source)
    previous = _state(record)
    database_path = Path(dead_letter_dir).parent / "delivery.sqlite3"
    if database_path.is_file():
        pending_dir = Path(spool_dir)
        if (
            pending_dir.name != "pending"
            and (pending_dir / "delivery.sqlite3").is_file()
        ):
            database_path = pending_dir / "delivery.sqlite3"
            pending_dir = pending_dir / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        destination = pending_dir / source.name
        if destination.exists():
            raise FileExistsError(f"spool destination exists: {destination}")
        identity = _identity(record)
        with sqlite3.connect(str(database_path), timeout=30.0) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM deliveries WHERE status='dead'
                   AND (envelope_id=? OR spool_path LIKE ?) LIMIT 1""",
                (identity.get("envelope_id"), f"%{source.name}"),
            ).fetchone()
            if row is None:
                raise ValueError(
                    "dead-letter record is missing from the delivery database"
                )
            os.replace(source, destination)
            now_epoch = datetime.now(timezone.utc).timestamp()
            connection.execute(
                """UPDATE deliveries SET status='pending', spool_path=?,
                   next_attempt_at=?, lease_owner=NULL, lease_until=NULL,
                   dead_at=NULL, last_error=NULL WHERE envelope_id=?""",
                (str(destination), now_epoch, row["envelope_id"]),
            )
        return {
            "ok": True,
            "path": str(destination),
            "previous_state": "dead_letter",
            "state": "spooled",
            **identity,
        }
    at = utc_now()
    history = record.setdefault("history", [])
    if not isinstance(history, list):
        history = record["history"] = []
    history.append(
        {
            "from": previous,
            "to": "spooled",
            "at": at,
            "reason": "dead_letter_requeue",
            "dead_letter_reason": record.get("dead_letter_reason"),
        }
    )
    record["state"] = "spooled"
    record["state_changed_at"] = at
    record["requeued_at"] = at
    for key in (
        "dead_lettered_at",
        "dead_letter_reason",
        "publishing_at",
        "publish_started_at",
        "lease_owner",
        "lease_expires_at",
        "next_attempt_at",
    ):
        record.pop(key, None)
    delivery = record.get("delivery")
    if isinstance(delivery, dict):
        delivery["state"] = "spooled"
        for key in (
            "publishing_at",
            "started_at",
            "lease_owner",
            "lease_expires_at",
            "next_attempt_at",
        ):
            delivery.pop(key, None)

    spool_dir.mkdir(parents=True, exist_ok=True)
    destination = spool_dir / source.name
    if destination.exists():
        existing = _read(destination)
        left = _identity(existing)
        right = _identity(record)
        comparable = [
            key for key in left if left[key] is not None and right[key] is not None
        ]
        if not comparable or not any(left[key] == right[key] for key in comparable):
            raise FileExistsError(
                f"spool destination exists for a different record: {destination}"
            )
        source.unlink()
        return {"ok": True, "already_spooled": True, "path": str(destination), **right}

    _atomic_write_json(source, record)
    os.replace(source, destination)
    return {
        "ok": True,
        "path": str(destination),
        "previous_state": previous,
        "state": "spooled",
        **_identity(record),
    }


def purge_dead_letters(
    dead_letter_dir: Path, *, confirm: bool = False
) -> dict[str, Any]:
    """Permanently remove all JSON dead letters, only with explicit confirmation."""
    if not confirm:
        raise ValueError("purge requires confirm=True (CLI: --confirm)")
    dead_letter_dir = Path(dead_letter_dir)
    paths = _paths(dead_letter_dir)
    removed: list[str] = []
    errors: list[dict[str, str]] = []
    database_path = dead_letter_dir.parent / "delivery.sqlite3"
    connection = (
        sqlite3.connect(str(database_path), timeout=30.0)
        if database_path.is_file()
        else None
    )
    try:
        if connection is not None:
            connection.execute("BEGIN IMMEDIATE")
        for path in paths:
            try:
                path.unlink()
                removed.append(path.name)
                if connection is not None:
                    connection.execute(
                        "DELETE FROM deliveries WHERE status='dead' AND spool_path LIKE ?",
                        (f"%{path.name}",),
                    )
            except OSError as exc:
                errors.append(
                    {"name": path.name, "error": f"{type(exc).__name__}: {exc}"}
                )
        if connection is not None:
            connection.commit()
    finally:
        if connection is not None:
            connection.close()
    return {
        "ok": not errors,
        "dead_letter_dir": str(dead_letter_dir),
        "purged": len(removed),
        "removed": removed,
        "errors": errors,
        "at": utc_now(),
    }


def _default_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage CRCP dead-letter records")
    parser.add_argument(
        "--dir",
        type=Path,
        default=_default_root() / "dead-letter",
        help="dead-letter directory",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list metadata for dead-letter records")
    inspect = sub.add_parser("inspect", help="inspect one redacted record")
    inspect.add_argument("entry", help="filename, event key, or envelope id")
    requeue = sub.add_parser("requeue", help="move one record back to the spool")
    requeue.add_argument("entry", help="filename, event key, or envelope id")
    requeue.add_argument("--spool", type=Path, default=_default_root() / "spool")
    purge = sub.add_parser("purge", help="permanently remove all dead letters")
    purge.add_argument(
        "--confirm", action="store_true", help="confirm permanent deletion"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "list":
            result = list_dead_letters(args.dir)
        elif args.command == "inspect":
            result = inspect_dead_letter(args.dir, args.entry)
        elif args.command == "requeue":
            result = requeue_dead_letter(args.dir, args.entry, args.spool)
        else:
            result = purge_dead_letters(args.dir, confirm=args.confirm)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok", True) else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
