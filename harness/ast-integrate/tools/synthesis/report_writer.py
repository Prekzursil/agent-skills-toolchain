"""Completion-report writer that is BLOCKED by the manifest gate (SYN-0019).

``write_completion_report(dest, payload, verification, write_time=...,
freshness_window_seconds=...)`` refuses to write unless the disk verification
in ``verification`` is PERMITTED *and* still inside its freshness window at
``write_time``. The gate logic lives in tools/command-center/manifest_gate.py;
this module is the writer-side entry point the final synthesis agent calls.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:  # the gate module lives beside the other command-center tools
    import manifest_gate as _gate
except ImportError:  # pragma: no cover - path not prepared by the caller
    _cc = Path(__file__).resolve().parents[1] / "command-center"
    if str(_cc) not in sys.path:
        sys.path.insert(0, str(_cc))
    import manifest_gate as _gate

verify_manifest = _gate.verify_manifest
authorize_write = _gate.authorize_write
PERMITTED = _gate.PERMITTED
BLOCKED = _gate.BLOCKED


def write_completion_report(
    dest: Path | str,
    payload: dict[str, Any] | None,
    verification: dict[str, Any],
    *,
    write_time: datetime | str | None = None,
    freshness_window_seconds: int | float | None = None,
) -> dict[str, Any]:
    """Gate-checked write. Returns the writer record: verdict, exit_code,
    wrote, output_exists, blocking_conditions, wall_clock_gap_seconds,
    freshness_window_seconds, write_time, verified_at, path."""
    return _gate.write_completion_report(
        dest,
        payload or {},
        verification,
        write_time=write_time,
        freshness_window_seconds=freshness_window_seconds,
    )


def verify_then_write(
    root: Path | str,
    manifest: Any,
    dest: Path | str,
    payload: dict[str, Any] | None,
    *,
    freshness_window_seconds: int | float = _gate.DEFAULT_FRESHNESS_WINDOW_SECONDS,
    default_min_bytes: int = _gate.DEFAULT_MIN_BYTES,
) -> dict[str, Any]:
    """One-shot convenience: verify the manifest now, then write immediately.
    The verification is re-run at report time by construction, so the only
    way to be BLOCKED here is a real defect on disk."""
    verification = _gate.verify_manifest(
        root,
        manifest,
        freshness_window_seconds=freshness_window_seconds,
        default_min_bytes=default_min_bytes,
    )
    record = write_completion_report(
        dest, payload, verification, freshness_window_seconds=freshness_window_seconds
    )
    record["verification"] = verification
    return record


__all__ = [
    "BLOCKED",
    "PERMITTED",
    "authorize_write",
    "verify_manifest",
    "verify_then_write",
    "write_completion_report",
]
