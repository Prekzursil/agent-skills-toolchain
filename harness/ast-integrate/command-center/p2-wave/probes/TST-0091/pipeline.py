#!/usr/bin/env python3
"""TST-0091 SUT: naive wait-all parallel() vs per-unit pipelines.

Failure class :11317: a barrier with no per-agent timeout deadlocks a cohort
on one hung unit. The target is a per-work-unit pipeline, a per-agent deadline,
and a null-tolerant fan-in that resolves with N-1 survivors plus one typed
timeout classification.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

TERMINAL = frozenset({"SUCCESS", "TIMEOUT", "FAILED"})


@dataclass
class UnitSpec:
    unit_id: str
    fn: Callable[[], Any]
    timeout_s: float


@dataclass
class UnitRecord:
    unit_id: str
    state: str
    classification: str
    payload: Any
    elapsed_s: float
    attributed: bool
    ledger_path: str | None = None
    written_monotonic: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def timeout_class(timeout_s: float) -> str:
    """Catalog failure class shape timeout-<n>s, with n the declared deadline."""
    if timeout_s == int(timeout_s):
        n = str(int(timeout_s))
    else:
        n = f"{timeout_s:g}"
    return f"timeout-{n}s"


def write_ledger(ledger_dir: Path | None, rec: UnitRecord, t0: float) -> UnitRecord:
    if ledger_dir is None:
        return rec
    ledger_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_dir / f"{rec.unit_id}.json"
    rec.ledger_path = str(path)
    rec.written_monotonic = time.monotonic() - t0
    path.write_text(json.dumps(rec.as_dict(), sort_keys=True) + "\n", encoding="utf-8")
    return rec


def read_ledger(ledger_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not ledger_dir.is_dir():
        return rows
    for path in sorted(ledger_dir.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(doc, dict):
            rows.append(doc)
    return rows


def naive_parallel(specs: list[UnitSpec], ledger_dir: Path | None = None) -> list[Any]:
    """Wait-all barrier with no per-agent timeout (the measured defect).

    ThreadPoolExecutor.map returns only after every callable finishes, so one
    hung unit blocks the whole batch. Results are held in memory until the
    last sibling completes — survivors are not durable while the hung unit
    is still awaited.
    """
    if not specs:
        return []
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(specs)) as pool:
        payloads = list(pool.map(lambda s: s.fn(), specs))
    if ledger_dir is not None:
        ledger_dir.mkdir(parents=True, exist_ok=True)
        for spec, payload in zip(specs, payloads):
            rec = UnitRecord(
                unit_id=spec.unit_id,
                state="SUCCESS",
                classification="completed",
                payload=payload,
                elapsed_s=time.monotonic() - t0,
                attributed=isinstance(payload, dict)
                and payload.get("unit_id") == spec.unit_id,
            )
            write_ledger(ledger_dir, rec, t0)
    return payloads


def _fan_in(records: list[UnitRecord], n: int) -> list[UnitRecord]:
    """Null-tolerant fan-in: TIMEOUT is a first-class record, not a poison None."""
    if len(records) != n:
        raise ValueError(f"fan-in expected {n} terminal records, got {len(records)}")
    for rec in records:
        if rec.state not in TERMINAL:
            raise ValueError(f"non-terminal {rec.unit_id} state={rec.state}")
        if rec.state == "TIMEOUT" and rec.payload is None:
            continue
    return records


def per_unit_pipeline(
    specs: list[UnitSpec],
    ledger_dir: Path | None = None,
    slice_s: float = 0.01,
    partial_after_s: float | None = None,
) -> dict[str, Any]:
    """Each unit has its own worker, deadline, and write-as-you-go ledger row.

    The barrier resolves when every unit is terminal (SUCCESS or TIMEOUT), not
    when every worker thread has exited. A hung worker is classified
    timeout-<n>s and left running; it does not delay sibling fan-in.
    """
    n = len(specs)
    t0 = time.monotonic()
    records: dict[str, UnitRecord] = {}
    partial: dict[str, Any] | None = None
    if n == 0:
        return {
            "resolved": True,
            "n": 0,
            "n_success": 0,
            "n_timeout": 0,
            "n_failed": 0,
            "records": [],
            "wall_s": 0.0,
            "partial": None,
            "ledger_dir": str(ledger_dir) if ledger_dir else None,
        }

    pool = ThreadPoolExecutor(max_workers=n)
    try:
        futures = {pool.submit(spec.fn): spec for spec in specs}
        deadline = {fut: t0 + spec.timeout_s for fut, spec in futures.items()}
        pending = set(futures)
        while pending:
            now = time.monotonic()
            if (
                partial is None
                and partial_after_s is not None
                and (now - t0) >= partial_after_s
            ):
                durable = read_ledger(ledger_dir) if ledger_dir is not None else []
                partial = {
                    "t_s": now - t0,
                    "n_durable": len(durable),
                    "durable_ids": sorted(
                        str(r.get("unit_id") or "") for r in durable
                    ),
                    "n_terminal_in_memory": len(records),
                }
            remaining = [deadline[f] - now for f in pending]
            wait_s = max(0.0, min(slice_s, min(remaining) if remaining else slice_s))
            done, still = wait(pending, timeout=wait_s, return_when=FIRST_COMPLETED)
            now = time.monotonic()
            for fut in done:
                spec = futures[fut]
                pending.discard(fut)
                if spec.unit_id in records:
                    continue
                elapsed = now - t0
                try:
                    payload = fut.result(timeout=0)
                    rec = UnitRecord(
                        unit_id=spec.unit_id,
                        state="SUCCESS",
                        classification="completed",
                        payload=payload,
                        elapsed_s=elapsed,
                        attributed=isinstance(payload, dict)
                        and payload.get("unit_id") == spec.unit_id,
                    )
                except Exception as exc:
                    rec = UnitRecord(
                        unit_id=spec.unit_id,
                        state="FAILED",
                        classification=f"failed-{type(exc).__name__}",
                        payload=None,
                        elapsed_s=elapsed,
                        attributed=True,
                    )
                records[spec.unit_id] = write_ledger(ledger_dir, rec, t0)
            now = time.monotonic()
            for fut in list(pending):
                spec = futures[fut]
                if now >= deadline[fut] and spec.unit_id not in records:
                    rec = UnitRecord(
                        unit_id=spec.unit_id,
                        state="TIMEOUT",
                        classification=timeout_class(spec.timeout_s),
                        payload=None,
                        elapsed_s=now - t0,
                        attributed=True,
                    )
                    records[spec.unit_id] = write_ledger(ledger_dir, rec, t0)
                    pending.discard(fut)
    finally:
        pool.shutdown(wait=False, cancel_futures=False)

    ordered = _fan_in([records[s.unit_id] for s in specs], n)
    n_success = sum(1 for r in ordered if r.state == "SUCCESS")
    n_timeout = sum(1 for r in ordered if r.state == "TIMEOUT")
    n_failed = sum(1 for r in ordered if r.state == "FAILED")
    return {
        "resolved": True,
        "n": n,
        "n_success": n_success,
        "n_timeout": n_timeout,
        "n_failed": n_failed,
        "records": [r.as_dict() for r in ordered],
        "wall_s": time.monotonic() - t0,
        "partial": partial,
        "ledger_dir": str(ledger_dir) if ledger_dir else None,
    }
