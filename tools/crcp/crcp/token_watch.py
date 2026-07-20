"""auth.json mtime watcher + stale-threshold alerts (no secrets)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .auth import codex_auth_status
from .envelope import utc_now


def watch_auth_json(
    *,
    codex_home: Path | None = None,
    interval_sec: float = 5.0,
    log_path: Path | None = None,
    on_change: Callable[[dict[str, Any]], None] | None = None,
    once: bool = False,
) -> dict[str, Any]:
    """Watch ~/.codex/auth.json. Logs events without secrets."""
    home = codex_home or Path.home() / ".codex"
    auth_path = home / "auth.json"
    root = Path(__file__).resolve().parents[1]
    log_path = log_path or (root / "reports" / "auth_watch_log.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    last_mtime: float | None = None
    if auth_path.is_file():
        last_mtime = auth_path.stat().st_mtime

    events: list[dict[str, Any]] = []

    def emit(event: dict[str, Any]) -> None:
        event = dict(event)
        event.setdefault("at", utc_now())
        events.append(event)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")
        if on_change:
            on_change(event)
        print(json.dumps(event, default=str), flush=True)

    def snapshot() -> dict[str, Any]:
        st = codex_auth_status(home)
        access = st.get("access_token") or {}
        return {
            "event": "auth_status",
            "status": st.get("status"),
            "file_mtime_utc": st.get("file_mtime_utc"),
            "last_refresh": st.get("last_refresh"),
            "last_refresh_age_days": st.get("last_refresh_age_days"),
            "would_proactive_refresh_by_age": st.get("would_proactive_refresh_by_age"),
            "access_seconds_until_exp": access.get("seconds_until_exp"),
            "access_ttl_hours_remaining": round((access.get("seconds_until_exp") or 0) / 3600, 2)
            if access.get("seconds_until_exp") is not None
            else None,
            "within_5min_of_exp": access.get("within_5min_of_exp"),
            "stale_warning_8d": bool(st.get("would_proactive_refresh_by_age")),
        }

    emit({"event": "watch_start", "auth_path": str(auth_path), **{k: v for k, v in snapshot().items() if k != "event"}})

    if once:
        return {"events": events, "log_path": str(log_path)}

    try:
        while True:
            if not auth_path.is_file():
                emit({"event": "auth_missing"})
                time.sleep(interval_sec)
                continue
            mtime = auth_path.stat().st_mtime
            if last_mtime is None or mtime != last_mtime:
                last_mtime = mtime
                snap = snapshot()
                snap["event"] = "auth_file_changed"
                emit(snap)
            else:
                # periodic soft alert near thresholds
                snap = snapshot()
                if snap.get("stale_warning_8d") or snap.get("within_5min_of_exp"):
                    snap["event"] = "auth_threshold_alert"
                    emit(snap)
            time.sleep(interval_sec)
    except KeyboardInterrupt:
        emit({"event": "watch_stop"})
        return {"events": events, "log_path": str(log_path)}
