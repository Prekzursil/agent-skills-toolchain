"""Logging / telemetry that redacts only at the sink."""
from __future__ import annotations

from sink_scrub import _emit


def log_error(message: str) -> str:
    return _emit(str(message))


def log_exception(exc: BaseException) -> str:
    return _emit(f"{type(exc).__name__}: {exc}")


def emit_telemetry(name: str, payload: dict) -> str:
    token = payload.get("token") if isinstance(payload, dict) else payload
    return _emit(f"telemetry {name} token={token}")
