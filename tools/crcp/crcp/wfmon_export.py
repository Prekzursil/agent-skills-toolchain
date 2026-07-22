"""Metadata-only CRCP health export for wfmon and cockpit consumers.

The exporter preserves the original ``wfmon_crcp_health.json`` top-level
fields while adding operational readiness, delivery backlog, SSE uncertainty,
and acknowledgement freshness.  Missing optional state is reported as unknown;
it is never converted to a healthy zero.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "crcp.wfmon.health.v2"
REDACTED = "[REDACTED]"
DEFAULT_POLL_INTERVAL_SECONDS = 60.0
DEFAULT_POLL_GRACE_SECONDS = 60.0

_SECRET_KEY = re.compile(
    r"(?:authorization|access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"bearer|jwt|secret|password|cookie|api[_-]?key|proof[_-]?token|"
    r"prepare[_-]?token|turnstile[_-]?token|conduit[_-]?token|resume[_-]?token)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_JWT = re.compile(
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
)
_INLINE_SECRET = re.compile(
    r"(?i)\b(authorization|access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"api[_-]?key|password|secret|proof[_-]?token|prepare[_-]?token|"
    r"resume[_-]?token)(\s*[=:]\s*)([^&\s,;]+)"
)
_UNCERTAIN = {"UNCERTAIN_ACCEPTED", "uncertain_accepted"}
_ACK_KEYS = ("last_ack_at", "last_acked_at", "acked_at", "delivered_at")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact(value: Any) -> Any:
    """Return a deep copy with credential-shaped keys and strings removed."""
    if isinstance(value, dict):
        return {
            str(key): REDACTED if _SECRET_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        cleaned = _BEARER.sub(f"Bearer {REDACTED}", value)
        cleaned = _JWT.sub(REDACTED, cleaned)
        return _INLINE_SECRET.sub(
            lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", cleaned
        )
    return value


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _timestamp(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except (ValueError, OverflowError):
            try:
                number = float(value)
                return number if math.isfinite(number) else None
            except ValueError:
                return None
    return None


def _age_seconds(value: Any, now_timestamp: float) -> float | None:
    parsed = _timestamp(value)
    return max(0.0, now_timestamp - parsed) if parsed is not None else None


def _health_rails(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = report.get("rows")
    if isinstance(rows, list):
        return {
            str(row.get("rail")): {
                "status": row.get("status", "UNKNOWN"),
                "ok": bool(row.get("ok")),
            }
            for row in rows
            if isinstance(row, dict) and row.get("rail")
        }
    rails = report.get("rails")
    if not isinstance(rails, dict):
        return {}
    compact: dict[str, dict[str, Any]] = {}
    for name, rail in rails.items():
        if not isinstance(rail, dict):
            continue
        status = rail.get("status", "UNKNOWN")
        compact[str(name)] = {
            "status": status,
            "ok": bool(rail.get("ok", status in ("LOGGED_IN", "EXPIRING_SOON"))),
        }
    return compact


def _auth_ready(report: dict[str, Any]) -> tuple[bool | None, str]:
    rails = _health_rails(report)
    auth = rails.get("codex_auth")
    if auth is None:
        return None, "codex_auth_missing"
    return bool(auth.get("ok")), str(auth.get("status", "UNKNOWN"))


def _rail_ready(report: dict[str, Any], name: str) -> tuple[bool | None, str]:
    rail = _health_rails(report).get(name)
    if rail is None:
        return None, f"{name}_missing"
    return bool(rail.get("ok")), str(rail.get("status", "UNKNOWN"))


def collect_backlog(database_path: Path | None, now_timestamp: float) -> dict[str, Any]:
    """Collect delivery queue metadata from a W1 ``delivery.sqlite3`` file."""
    unknown = {
        "known": False,
        "items": None,
        "bytes": None,
        "oldest_age_seconds": None,
        "by_status": {},
    }
    if database_path is None or not database_path.is_file():
        return unknown
    try:
        uri = database_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=2.0)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS item_count,
                       COALESCE(SUM(size_bytes), 0) AS byte_count,
                       MIN(created_at) AS oldest
                FROM deliveries GROUP BY status
                """
            ).fetchall()
        finally:
            connection.close()
    except (OSError, sqlite3.Error):
        return unknown

    by_status = {
        str(row["status"]): {
            "items": int(row["item_count"]),
            "bytes": int(row["byte_count"]),
        }
        for row in rows
    }
    active = [row for row in rows if row["status"] in ("pending", "leased")]
    oldest = min(
        (float(row["oldest"]) for row in active if row["oldest"] is not None),
        default=None,
    )
    return {
        "known": True,
        "items": sum(int(row["item_count"]) for row in active),
        "bytes": sum(int(row["byte_count"]) for row in active),
        "oldest_age_seconds": max(0.0, now_timestamp - oldest)
        if oldest is not None
        else 0.0,
        "by_status": by_status,
    }


def _walk_uncertain(value: Any) -> int:
    if isinstance(value, dict):
        direct = value.get("uncertain_sse_count")
        if isinstance(direct, int) and not isinstance(direct, bool) and direct >= 0:
            return direct
        for key in (
            "classification",
            "terminal_classification",
            "sse_status",
            "outcome",
        ):
            if value.get(key) in _UNCERTAIN:
                return 1
        return sum(_walk_uncertain(item) for item in value.values())
    if isinstance(value, list):
        return sum(_walk_uncertain(item) for item in value)
    return 0


def collect_sse_uncertain(paths: Iterable[Path]) -> dict[str, Any]:
    """Count uncertain SSE outcomes in explicit, metadata/report JSON inputs."""
    total = 0
    files_read = 0
    for path in paths:
        value = _read_json(path)
        if value is None:
            continue
        files_read += 1
        total += _walk_uncertain(value)
    return {
        "known": files_read > 0,
        "count": total if files_read else None,
        "files_read": files_read,
    }


def _find_ack_values(value: Any) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _ACK_KEYS:
                found.append(item)
            found.extend(_find_ack_values(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_find_ack_values(item))
    return found


def collect_last_ack(
    publish_state: dict[str, Any] | None,
    database_path: Path | None,
    now_timestamp: float,
) -> dict[str, Any]:
    """Return newest durable delivery acknowledgement timestamp and age."""
    timestamps: list[float] = []
    if publish_state is not None:
        for value in _find_ack_values(publish_state):
            parsed = _timestamp(value)
            if parsed is not None:
                timestamps.append(parsed)
        published = publish_state.get("published_ids")
        if isinstance(published, dict):
            for record in published.values():
                if isinstance(record, dict):
                    parsed = _timestamp(record.get("at"))
                    if parsed is not None:
                        timestamps.append(parsed)

    if database_path is not None and database_path.is_file():
        try:
            uri = database_path.resolve().as_uri() + "?mode=ro"
            connection = sqlite3.connect(uri, uri=True, timeout=2.0)
            try:
                row = connection.execute(
                    "SELECT MAX(delivered_at) FROM deliveries WHERE status = 'delivered'"
                ).fetchone()
            finally:
                connection.close()
            if row and row[0] is not None:
                timestamps.append(float(row[0]))
        except (OSError, sqlite3.Error, TypeError, ValueError):
            pass

    newest = max(timestamps, default=None)
    if newest is None:
        return {"known": False, "at": None, "age_seconds": None}
    return {
        "known": True,
        "at": datetime.fromtimestamp(newest, timezone.utc).isoformat(),
        "age_seconds": max(0.0, now_timestamp - newest),
    }


def build_readyz(
    health_report: dict[str, Any],
    live_state: dict[str, Any] | None,
    backlog: dict[str, Any],
    *,
    now_timestamp: float,
    poll_interval_seconds: float,
    poll_grace_seconds: float,
    max_backlog_age_seconds: float | None = None,
) -> dict[str, Any]:
    """Evaluate auth, poll freshness, lease, and optional backlog age gates."""
    checks: dict[str, dict[str, Any]] = {}
    auth_ok, auth_detail = _auth_ready(health_report)
    checks["auth"] = {"ok": auth_ok, "detail": auth_detail}
    bus_ok, bus_detail = _rail_ready(health_report, "agent_mail")
    checks["agent_mail"] = {"ok": bus_ok, "detail": bus_detail}

    stale_after = 2.0 * poll_interval_seconds + poll_grace_seconds
    poll_age = _age_seconds(
        live_state.get("last_poll_at") if isinstance(live_state, dict) else None,
        now_timestamp,
    )
    checks["poll_fresh"] = {
        "ok": poll_age <= stale_after if poll_age is not None else None,
        "age_seconds": poll_age,
        "stale_after_seconds": stale_after,
    }

    lease_ok: bool | None = None
    lease_detail = "not_reported"
    if isinstance(live_state, dict):
        if isinstance(live_state.get("lease_ok"), bool):
            lease_ok = live_state["lease_ok"]
            lease_detail = "lease_ok"
        elif live_state.get("lease_lost") is True:
            lease_ok = False
            lease_detail = "lease_lost"
        elif live_state.get("lease_owner") or live_state.get("lease_acquired_at"):
            lease_ok = True
            lease_detail = "lease_present"
    checks["lease"] = {"ok": lease_ok, "detail": lease_detail}

    if max_backlog_age_seconds is not None:
        age = backlog.get("oldest_age_seconds") if backlog.get("known") else None
        checks["backlog_age"] = {
            "ok": age <= max_backlog_age_seconds
            if isinstance(age, (int, float))
            else None,
            "age_seconds": age,
            "max_age_seconds": max_backlog_age_seconds,
        }

    failed = sorted(name for name, check in checks.items() if check.get("ok") is False)
    unknown = sorted(name for name, check in checks.items() if check.get("ok") is None)
    ready = not failed and not unknown
    return {
        "ready": ready,
        "status": "READY" if ready else "NOT_READY",
        "failed_checks": failed,
        "unknown_checks": unknown,
        "checks": checks,
    }


def build_wfmon_report(
    health_report: dict[str, Any],
    *,
    root: Path | None = None,
    live_state_path: Path | None = None,
    delivery_database_path: Path | None = None,
    publish_state_path: Path | None = None,
    sse_metric_paths: Iterable[Path] = (),
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    poll_grace_seconds: float = DEFAULT_POLL_GRACE_SECONDS,
    max_backlog_age_seconds: float | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a secret-safe wfmon document from persisted CRCP metadata."""
    if poll_interval_seconds <= 0 or poll_grace_seconds < 0:
        raise ValueError("poll interval must be positive and grace non-negative")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    now_timestamp = current.timestamp()
    base = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    live_path = live_state_path or (base / "reports" / "live_bridge_state.json")
    publish_path = publish_state_path or (base / "outbox" / ".publish_state.json")
    delivery_path = delivery_database_path
    if delivery_path is None:
        candidates = (
            base / "spool" / "delivery.sqlite3",
            base / "outbox" / "delivery.sqlite3",
            base / "reports" / "delivery.sqlite3",
        )
        delivery_path = next(
            (path for path in candidates if path.is_file()), candidates[0]
        )

    live_state = _read_json(live_path)
    publish_state = _read_json(publish_path)
    backlog = collect_backlog(delivery_path, now_timestamp)
    uncertain = collect_sse_uncertain(sse_metric_paths)
    last_ack = collect_last_ack(publish_state, delivery_path, now_timestamp)
    readyz = build_readyz(
        health_report,
        live_state,
        backlog,
        now_timestamp=now_timestamp,
        poll_interval_seconds=poll_interval_seconds,
        poll_grace_seconds=poll_grace_seconds,
        max_backlog_age_seconds=max_backlog_age_seconds,
    )
    report = {
        "schema": SCHEMA,
        "source": "crcp.health",
        "probed_at": health_report.get("probed_at") or current.isoformat(),
        "overall": health_report.get("overall", "UNKNOWN"),
        "rails": _health_rails(health_report),
        "readyz": readyz,
        "backlog": backlog,
        "sse": {"uncertain": uncertain},
        "last_ack": last_ack,
        "metrics": {
            "backlog_items": backlog.get("items"),
            "backlog_bytes": backlog.get("bytes"),
            "oldest_backlog_age_seconds": backlog.get("oldest_age_seconds"),
            "sse_uncertain_count": uncertain.get("count"),
            "last_ack_age_seconds": last_ack.get("age_seconds"),
        },
    }
    return redact(report)


def write_wfmon_report(report: dict[str, Any], path: Path) -> Path:
    """Atomically write a redacted wfmon report on Windows or POSIX."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(redact(report), indent=2, sort_keys=True) + "\n"
    fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=str(destination.parent)
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary_path), str(destination))
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
    return destination


def write_wfmon_snippet(report: dict[str, Any], path: Path, **kwargs: Any) -> Path:
    """Drop-in replacement for ``health.write_wfmon_snippet``."""
    return write_wfmon_report(build_wfmon_report(report, **kwargs), path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export CRCP health metadata for wfmon"
    )
    parser.add_argument(
        "--health", type=Path, required=True, help="health_live.json input"
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="wfmon JSON destination"
    )
    parser.add_argument("--root", type=Path, help="CRCP root containing reports/outbox")
    parser.add_argument("--live-state", type=Path)
    parser.add_argument("--delivery-db", type=Path)
    parser.add_argument("--publish-state", type=Path)
    parser.add_argument("--sse-metrics", type=Path, action="append", default=[])
    parser.add_argument(
        "--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL_SECONDS
    )
    parser.add_argument("--poll-grace", type=float, default=DEFAULT_POLL_GRACE_SECONDS)
    parser.add_argument("--max-backlog-age", type=float)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    health_report = _read_json(args.health)
    if health_report is None:
        raise SystemExit(f"health input is missing or invalid JSON: {args.health}")
    report = build_wfmon_report(
        health_report,
        root=args.root,
        live_state_path=args.live_state,
        delivery_database_path=args.delivery_db,
        publish_state_path=args.publish_state,
        sse_metric_paths=args.sse_metrics,
        poll_interval_seconds=args.poll_interval,
        poll_grace_seconds=args.poll_grace,
        max_backlog_age_seconds=args.max_backlog_age,
    )
    write_wfmon_report(report, args.output)
    return 0 if report["readyz"]["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SCHEMA",
    "build_readyz",
    "build_wfmon_report",
    "collect_backlog",
    "collect_last_ack",
    "collect_sse_uncertain",
    "redact",
    "write_wfmon_report",
    "write_wfmon_snippet",
]
