"""Unified multi-rail health probes for CRCP / wfmon."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .auth import (
    agent_mail_status,
    chatgpt_bridge_status,
    codex_auth_status,
    databricks_auth_status,
)
from .wfmon_export import (
    redact,
    write_wfmon_snippet as _write_operational_wfmon_snippet,
)


DEFAULT_POLL_INTERVAL_SECONDS = 60.0
DEFAULT_POLL_GRACE_SECONDS = 60.0
HEALTHY_STATUSES = ("LOGGED_IN", "EXPIRING_SOON")


def _crcp_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _utc_now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current


def _timestamp(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except (ValueError, OverflowError):
            try:
                parsed = float(value)
                return parsed if math.isfinite(parsed) else None
            except ValueError:
                return None
    return None


def _read_live_state(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, "state_missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        return None, f"state_unreadable:{type(exc).__name__}"
    if not isinstance(value, dict):
        return None, "state_not_object"
    return value, None


def _counter(state: dict[str, Any] | None, name: str) -> int | None:
    value = state.get(name) if state is not None else None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _metrics_snapshot(
    state: dict[str, Any] | None,
    *,
    now_timestamp: float,
) -> dict[str, Any]:
    last_poll = _timestamp(state.get("last_poll_at")) if state is not None else None
    return {
        "polls": _counter(state, "polls"),
        "fetches": _counter(state, "fetches"),
        "publishes": _counter(state, "publishes"),
        "last_poll_age_s": max(0.0, now_timestamp - last_poll)
        if last_poll is not None
        else None,
    }


def livez() -> dict[str, Any]:
    """Return a cheap process-local liveness check with no I/O or rail probes."""
    live = threading.current_thread().is_alive()
    return {
        "live": live,
        "status": "LIVE" if live else "NOT_LIVE",
        "pid": os.getpid(),
        "checks": {"process": {"ok": live}},
    }


def readyz(
    state_path: Path | None = None,
    *,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    poll_grace_seconds: float = DEFAULT_POLL_GRACE_SECONDS,
    auth_report: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Gate readiness on auth, durable poll freshness, and sticky poll errors."""
    if poll_interval_seconds <= 0 or poll_grace_seconds < 0:
        raise ValueError("poll interval must be positive and grace non-negative")

    current = _utc_now(now)
    path = state_path or (_crcp_root() / "reports" / "live_bridge_state.json")
    state, state_error = _read_live_state(Path(path))
    auth = auth_report if auth_report is not None else codex_auth_status()
    auth_status = (
        str(auth.get("status", "UNKNOWN")) if isinstance(auth, dict) else "UNKNOWN"
    )
    auth_ok = auth_status in HEALTHY_STATUSES
    metrics = _metrics_snapshot(state, now_timestamp=current.timestamp())
    stale_after = 2.0 * poll_interval_seconds + poll_grace_seconds
    poll_age = metrics["last_poll_age_s"]
    poll_fresh = isinstance(poll_age, (int, float)) and poll_age <= stale_after
    last_error = state.get("last_error") if state is not None else None
    error_clear = not bool(last_error)

    checks = {
        "auth": {"ok": auth_ok, "status": auth_status},
        "state": {"ok": state_error is None, "detail": state_error or "loaded"},
        "poll_fresh": {
            "ok": poll_fresh,
            "age_s": poll_age,
            "stale_after_s": stale_after,
        },
        "last_error_clear": {
            "ok": error_clear,
            "detail": redact(last_error) if last_error else None,
        },
    }
    failed = [name for name, check in checks.items() if not check["ok"]]
    ready = not failed
    return {
        "ready": ready,
        "status": "GREEN" if ready else "RED",
        "probed_at": current.isoformat(),
        "state_path": str(path),
        "failed_checks": failed,
        "checks": checks,
        "metrics": metrics,
    }


def claude_cli_status() -> dict[str, Any]:
    out: dict[str, Any] = {"rail": "claude", "status": "UNKNOWN", "signals": []}
    path = shutil.which("claude")
    if not path:
        out["status"] = "MISSING"
        out["signals"].append("claude_cli_not_on_path")
        return out
    out["cli_path"] = path
    out["signals"].append("cli_on_path")
    try:
        proc = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        version = (proc.stdout or proc.stderr or "").strip().splitlines()[:1]
        out["version_preview"] = version[0] if version else None
        out["cli_exit"] = proc.returncode
        out["status"] = "LOGGED_IN" if proc.returncode == 0 else "UNKNOWN"
        if proc.returncode == 0:
            out["signals"].append("version_ok")
    except Exception as exc:
        out["signals"].append(f"error:{type(exc).__name__}")
    out["settings_present"] = (Path.home() / ".claude" / "settings.json").is_file()
    return out


def codex_cli_status() -> dict[str, Any]:
    out: dict[str, Any] = {"rail": "codex_cli", "status": "UNKNOWN", "signals": []}
    candidates: list[str] = []
    discovered = shutil.which("codex")
    if discovered:
        candidates.append(discovered)
    for candidate in (
        Path.home() / "AppData/Roaming/npm/codex.cmd",
        Path.home() / "AppData/Roaming/npm/codex",
        Path.home() / ".local/bin/codex",
    ):
        if candidate.is_file():
            candidates.append(str(candidate))
    paths = list(dict.fromkeys(candidates))
    if not paths:
        out["status"] = "MISSING"
        out["signals"].append("codex_not_on_path")
        return out
    last_error = None
    for path in paths:
        out["cli_path"] = path
        try:
            command = (
                ["cmd", "/c", path, "--version"]
                if path.lower().endswith(".cmd")
                else [path, "--version"]
            )
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            preview = (proc.stdout or proc.stderr or "").strip().splitlines()[:1]
            out["version_preview"] = preview
            out["cli_exit"] = proc.returncode
            if proc.returncode == 0:
                out["status"] = "LOGGED_IN"
                out["signals"].append("version_ok")
                return out
            last_error = f"exit_{proc.returncode}"
        except Exception as exc:
            last_error = type(exc).__name__
    out["signals"].append(f"version_fail:{last_error}")
    return out


def full_health(
    *,
    state_path: Path | None = None,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    poll_grace_seconds: float = DEFAULT_POLL_GRACE_SECONDS,
    poller_expected: bool = True,
) -> dict[str, Any]:
    """Probe rails and combine critical failures with poller readiness."""
    rails = {
        "codex_auth": codex_auth_status(),
        "codex_cli": codex_cli_status(),
        "claude_cli": claude_cli_status(),
        "databricks": databricks_auth_status(),
        "agent_mail": agent_mail_status(),
        "chatgpt_live_bridge": chatgpt_bridge_status(),
    }
    rows = []
    for name, rail in rails.items():
        status = rail.get("status", "UNKNOWN")
        rows.append(
            {
                "rail": name,
                "status": status,
                "ok": status in HEALTHY_STATUSES,
                "signals": redact(rail.get("signals", [])[:6]),
            }
        )

    readiness = readyz(
        state_path,
        poll_interval_seconds=poll_interval_seconds,
        poll_grace_seconds=poll_grace_seconds,
        auth_report=rails["codex_auth"],
    )
    by_name = {row["rail"]: row for row in rows}
    critical = ("codex_auth", "agent_mail")
    critical_ok = all(by_name[name]["ok"] for name in critical)
    bridge_ok = by_name["chatgpt_live_bridge"]["ok"]
    poller_ok = readiness["ready"] if poller_expected else True
    if not critical_ok:
        overall = "RED"
    elif bridge_ok and poller_ok:
        overall = "GREEN"
    else:
        overall = "YELLOW"

    return {
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "overall": overall,
        "livez": livez(),
        "readyz": readiness,
        "poller_expected": poller_expected,
        "metrics": readiness["metrics"],
        "critical_rails": list(critical),
        "rows": rows,
        "rails": redact(rails),
    }


def health_table(report: dict[str, Any]) -> str:
    lines = [
        f"CRCP health overall={report.get('overall')} at {report.get('probed_at')}",
        f"{'RAIL':<22} {'STATUS':<18} OK  DETAIL",
        "-" * 78,
    ]
    rails = report.get("rails") or {}
    for row in report.get("rows") or []:
        detail = ",".join(str(item) for item in (row.get("signals") or []))[:36]
        if row["rail"] == "codex_auth":
            codex_detail = rails.get("codex_auth") or {}
            auth_value = (
                codex_detail.get("access_token")
                if isinstance(codex_detail, dict)
                else None
            )
            auth = auth_value if isinstance(auth_value, dict) else {}
            seconds = auth.get("seconds_until_exp")
            age = (
                codex_detail.get("last_refresh_age_days")
                if isinstance(codex_detail, dict)
                else None
            )
            stale = (
                codex_detail.get("would_proactive_refresh_by_age")
                if isinstance(codex_detail, dict)
                else None
            )
            if seconds is not None:
                detail = f"ttl={seconds / 3600:.1f}h age={age}d stale8d={stale}"
        lines.append(
            f"{row['rail']:<22} {row['status']:<18} "
            f"{'Y' if row['ok'] else 'N'}   {detail}"
        )

    readiness = report.get("readyz") or {}
    metrics = report.get("metrics") or readiness.get("metrics") or {}
    detail = (
        f"polls={metrics.get('polls')} fetches={metrics.get('fetches')} "
        f"pub={metrics.get('publishes')} age={metrics.get('last_poll_age_s')}s"
    )
    lines.append(
        f"{'live_poller':<22} {readiness.get('status', 'UNKNOWN'):<18} "
        f"{'Y' if readiness.get('ready') else 'N'}   {detail}"
    )
    return "\n".join(lines)


def write_wfmon_snippet(report: dict[str, Any], path: Path) -> Path:
    """Write the v2 metadata-only operational feed using existing CLI wiring."""
    return _write_operational_wfmon_snippet(report, path)


__all__ = [
    "DEFAULT_POLL_GRACE_SECONDS",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "claude_cli_status",
    "codex_cli_status",
    "full_health",
    "health_table",
    "livez",
    "readyz",
    "write_wfmon_snippet",
]
