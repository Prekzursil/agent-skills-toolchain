"""Recorded silent-failure and healthy traces for ARC-0033 both-states.

Traces are append-only ledger JSON objects. `mtime` is a decoy: the stalled
and completed hung-unit pair share the same mtime so an mtime-only detector
cannot tell them apart.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TRACE_DIR = HERE / "fixtures" / "traces"

SHARED_MTIME = 1_000.0  # identical on stalled vs completed hung-unit pair


def _hb(t: float, seq: int, monitor_id: str = "mon-1") -> dict[str, Any]:
    return {
        "kind": "monitor.heartbeat",
        "t": t,
        "monitor_id": monitor_id,
        "heartbeat_seq": seq,
        "mtime": SHARED_MTIME,
    }


def _claim(
    t: float,
    unit_id: str,
    *,
    monitor_id: str = "mon-1",
    batch_id: str | None = None,
    deadline_t: float | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "kind": "unit.claimed",
        "t": t,
        "unit_id": unit_id,
        "monitor_id": monitor_id,
        "mtime": SHARED_MTIME,
    }
    if batch_id is not None:
        row["batch_id"] = batch_id
    if deadline_t is not None:
        row["deadline_t"] = deadline_t
    return row


def _progress(t: float, unit_id: str, token: int) -> dict[str, Any]:
    return {
        "kind": "unit.progress",
        "t": t,
        "unit_id": unit_id,
        "progress_token": token,
        "cpu_delta_ms": 12,
        "bytes_written_delta": 64,
        "mtime": SHARED_MTIME,
    }


def _terminal(t: float, unit_id: str, state: str, fencing_token: int = 1) -> dict[str, Any]:
    return {
        "kind": "unit.terminal",
        "t": t,
        "unit_id": unit_id,
        "state": state,
        "fencing_token": fencing_token,
        "mtime": SHARED_MTIME,
    }


def monitor_dies_bad() -> list[dict[str, Any]]:
    """Heartbeats stop; remote unit keeps producing progress. Measured TST-0089 class."""
    return [
        _claim(0.0, "U-remote"),
        _hb(0.0, 1),
        _progress(0.4, "U-remote", 1),
        _hb(1.0, 2),
        _progress(1.4, "U-remote", 2),
        _hb(2.0, 3),
        _progress(2.4, "U-remote", 3),
        # monitor dead after t=2; work continues
        _progress(4.0, "U-remote", 4),
        _progress(5.5, "U-remote", 5),
        _progress(7.0, "U-remote", 6),
    ]


def monitor_dies_good() -> list[dict[str, Any]]:
    """Heartbeats continue for as long as progress continues."""
    return [
        _claim(0.0, "U-remote"),
        _hb(0.0, 1),
        _progress(0.4, "U-remote", 1),
        _hb(1.0, 2),
        _progress(1.4, "U-remote", 2),
        _hb(2.0, 3),
        _progress(2.4, "U-remote", 3),
        _hb(4.0, 4),
        _progress(4.0, "U-remote", 4),
        _hb(5.5, 5),
        _progress(5.5, "U-remote", 5),
        _hb(7.0, 6),
        _progress(7.0, "U-remote", 6),
        _terminal(7.2, "U-remote", "SUCCESS"),
        _hb(7.3, 7),
    ]


def harvest_noop_bad() -> list[dict[str, Any]]:
    """Exit 0, dest already had files, delta empty. IMP-0431 silent-noop-harvest."""
    return [
        {
            "kind": "harvest.attempt",
            "t": 1.0,
            "harvest_id": "H-empty",
            "process_exit_code": 0,
            "delta_files": 0,
            "delta_bytes": 0,
            "dest_preexisting_files": 3,
            "mtime": SHARED_MTIME,
        }
    ]


def harvest_noop_good() -> list[dict[str, Any]]:
    return [
        {
            "kind": "harvest.attempt",
            "t": 1.0,
            "harvest_id": "H-full",
            "process_exit_code": 0,
            "delta_files": 3,
            "delta_bytes": 4096,
            "dest_preexisting_files": 0,
            "mtime": SHARED_MTIME,
        }
    ]


def hung_blocks_bad() -> list[dict[str, Any]]:
    """wait-all, one hang past per-unit deadline, siblings unfinished in ledger."""
    return [
        {
            "kind": "batch.open",
            "t": 0.0,
            "batch_id": "B-waitall",
            "barrier_mode": "wait-all",
            "mtime": SHARED_MTIME,
        },
        _claim(0.0, "U-hang", batch_id="B-waitall", deadline_t=1.0),
        _claim(0.0, "U-sib", batch_id="B-waitall", deadline_t=1.0),
        _progress(0.4, "U-sib", 1),
        # sibling finished in RAM only — no unit.terminal (phase-memory wait-all)
        _progress(0.2, "U-hang", 1),
        {"kind": "clock", "t": 5.0, "mtime": SHARED_MTIME},
    ]


def hung_blocks_good() -> list[dict[str, Any]]:
    """Per-unit pipeline: hung unit TIMEOUT, sibling SUCCESS, batch closed.

    Same SHARED_MTIME as the bad hung trace so mtime-only cannot distinguish.
    """
    return [
        {
            "kind": "batch.open",
            "t": 0.0,
            "batch_id": "B-perunit",
            "barrier_mode": "per-unit",
            "mtime": SHARED_MTIME,
        },
        _claim(0.0, "U-hang", batch_id="B-perunit", deadline_t=1.0),
        _claim(0.0, "U-sib", batch_id="B-perunit", deadline_t=1.0),
        _progress(0.4, "U-sib", 1),
        _terminal(0.5, "U-sib", "SUCCESS"),
        _progress(0.2, "U-hang", 1),
        _terminal(1.05, "U-hang", "TIMEOUT"),
        {
            "kind": "batch.close",
            "t": 1.1,
            "batch_id": "B-perunit",
            "mtime": SHARED_MTIME,
        },
        {"kind": "clock", "t": 5.0, "mtime": SHARED_MTIME},
    ]


def dup_catalog_bad() -> list[dict[str, Any]]:
    return [
        {
            "kind": "catalog.merge",
            "t": 0.5,
            "merge_id": "M-collide",
            "duplicate_ids": ["ARC-0001", "IMP-0001"],
            "mtime": SHARED_MTIME,
        }
    ]


def dup_catalog_good() -> list[dict[str, Any]]:
    return [
        {
            "kind": "catalog.merge",
            "t": 0.5,
            "merge_id": "M-clean",
            "duplicate_ids": [],
            "mtime": SHARED_MTIME,
        }
    ]


def partial_no_sentinel_bad() -> list[dict[str, Any]]:
    return [
        {
            "kind": "artifact.observe",
            "t": 1.0,
            "unit_id": "U-partial",
            "bytes": 2048,
            "sentinel_present": False,
            "completion_predicate": False,
            "mtime": SHARED_MTIME,
        }
    ]


def partial_no_sentinel_good() -> list[dict[str, Any]]:
    return [
        {
            "kind": "artifact.observe",
            "t": 1.0,
            "unit_id": "U-complete",
            "bytes": 2048,
            "sentinel_present": True,
            "completion_predicate": True,
            "mtime": SHARED_MTIME,
        }
    ]


def sentinel_on_partial_bad() -> list[dict[str, Any]]:
    """Reviewer mode: SUCCESS: token on a file that fails the completion predicate."""
    return [
        {
            "kind": "artifact.observe",
            "t": 1.0,
            "unit_id": "U-forged",
            "bytes": 12,
            "sentinel_present": True,
            "completion_predicate": False,
            "mtime": SHARED_MTIME,
        }
    ]


def sentinel_on_partial_good() -> list[dict[str, Any]]:
    return partial_no_sentinel_good()


PAIRS: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]] = {
    "FM-MONITOR-DIES": (monitor_dies_bad(), monitor_dies_good()),
    "FM-HARVEST-NOOP": (harvest_noop_bad(), harvest_noop_good()),
    "FM-HUNG-BLOCKS-BATCH": (hung_blocks_bad(), hung_blocks_good()),
    "FM-DUP-CATALOG": (dup_catalog_bad(), dup_catalog_good()),
    "FM-PARTIAL-NO-SENTINEL": (partial_no_sentinel_bad(), partial_no_sentinel_good()),
    "FM-SENTINEL-ON-PARTIAL": (sentinel_on_partial_bad(), sentinel_on_partial_good()),
}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    path.write_text(body, encoding="utf-8")


def ensure_on_disk() -> list[str]:
    written: list[str] = []
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    for mode_id, (bad, good) in PAIRS.items():
        slug = mode_id.lower()
        bp = TRACE_DIR / f"{slug}.bad.jsonl"
        gp = TRACE_DIR / f"{slug}.good.jsonl"
        write_jsonl(bp, bad)
        write_jsonl(gp, good)
        written.extend([str(bp), str(gp)])
    return written
