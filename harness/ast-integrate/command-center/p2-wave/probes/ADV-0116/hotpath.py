#!/usr/bin/env python3
"""Shared ADV-0116 hot-path instrumentation.

Repo `platform/` shadows stdlib `platform`, which breaks jsonschema/uuid.
Unshadow before importing completion_predicate.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0116"
FX_SENTINEL = "SUCCESS:FX-ADV-0116"
ART_REL = "artifact.json"
SCHEMA_REL = "artifact.schema.json"

# 1x = one wave of 8 unit-completion cycles (IMP-0429 concurrent-session design
# point). 10x/100x scale event count, not process count (host-bound).
LOADS = (("1x", 8), ("10x", 80), ("100x", 800))
SCALE_WRITERS = (1, 2, 4, 8)
SCALE_PER_WRITER = 80
INTEGRITY_WRITERS = 8
INTEGRITY_PER = 100
MUTANT_WRITERS = 8
MUTANT_PER = 80

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["unit_id", "sentinel", "kind", "payload"],
    "properties": {
        "unit_id": {"type": "string"},
        "sentinel": {"type": "string"},
        "kind": {"const": "fixture"},
        "payload": {"type": "string"},
    },
    "additionalProperties": True,
}


def unshadow_stdlib_platform() -> None:
    keep: list[str] = []
    for entry in sys.path:
        if entry in ("", "."):
            continue
        try:
            if Path(entry).resolve() == REPO:
                continue
        except OSError:
            pass
        keep.append(entry)
    sys.path[:] = keep
    for name in list(sys.modules):
        if name == "platform" or name.startswith("platform."):
            mod = sys.modules[name]
            file = getattr(mod, "__file__", None) or ""
            if str(REPO) in str(file):
                del sys.modules[name]


unshadow_stdlib_platform()
sys.path.insert(0, str(REPO / "platform" / "lib"))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import completion_predicate as cp  # noqa: E402
import event_log as elog  # noqa: E402


def _digest(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def gold_fixture(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    (root / SCHEMA_REL).write_text(json.dumps(SCHEMA, indent=2) + "\n", encoding="utf-8")
    artifact = {
        "unit_id": "FX-ADV-0116",
        "sentinel": FX_SENTINEL,
        "kind": "fixture",
        "payload": "P" * 180,
    }
    raw = (json.dumps(artifact, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (root / ART_REL).write_bytes(raw)
    digest, size = _digest(raw)
    receipt = {
        "schema_version": 1,
        "unit_id": "FX-ADV-0116",
        "state": "SUCCESS",
        "sentinel": FX_SENTINEL,
        "min_bytes_threshold": 128,
        "artifact_schema": SCHEMA_REL,
        "output_schema": SCHEMA_REL,
        "artifacts": [
            {
                "path": ART_REL,
                "role": "primary",
                "exists": True,
                "sha256": digest,
                "bytes": size,
            }
        ],
        "evidence": [
            {
                "claim": "fixture produced a measurable artifact",
                "verdict": "CONFIRMED",
                "anchor": f"{ART_REL}:1",
                "probes": [
                    {"role": "source", "method": "file-read", "command": "stat artifact.json"},
                    {"role": "verifier", "method": "sha256", "command": "sha256sum artifact.json"},
                ],
            }
        ],
        "tests": [{"id": "t-gold", "command": "true", "result": "PASS"}],
        "negative_controls": [
            {
                "id": "c-both",
                "kind": "known-broken-fixture",
                "description": "detector fires on missing artifact and is silent on gold",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "fixture-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "defects": [],
    }
    (root / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def _integrity(scan: dict[str, Any], expected: int) -> dict[str, Any]:
    parsed = int(scan.get("parsed") or 0)
    torn = int(scan.get("torn") or 0)
    lines = int(scan.get("line_count") or 0)
    uniq = int(scan.get("unique_writer_seq") or 0)
    all_present = parsed == expected and torn == 0 and lines == expected and uniq == expected
    return {
        "expected": expected,
        "line_count": lines,
        "parsed": parsed,
        "torn": torn,
        "unique_writer_seq": uniq,
        "all_present": all_present,
        "parseable": torn == 0 and parsed == lines,
    }


def _rusage_delta(before: Any, after: Any) -> dict[str, int]:
    return {
        "ru_inblock": int(after.ru_inblock - before.ru_inblock),
        "ru_oublock": int(after.ru_oublock - before.ru_oublock),
        "ru_nvcsw": int(after.ru_nvcsw - before.ru_nvcsw),
        "ru_nivcsw": int(after.ru_nivcsw - before.ru_nivcsw),
    }


def profile_sequential(n: int, *, label: str) -> dict[str, Any]:
    import resource

    with tempfile.TemporaryDirectory(prefix=f"adv0116-{label}-") as tmp:
        root = Path(tmp)
        receipt = gold_fixture(root)
        log_path = root / "EVENTS.jsonl"
        pred = ser = app = 0.0
        ru0 = resource.getrusage(resource.RUSAGE_SELF)
        wall0 = time.perf_counter()
        v_last = None
        with elog.EventLog(log_path, atomic=True) as log:
            for seq in range(n):
                t0 = time.perf_counter()
                v_last = cp.evaluate(receipt, repo=root)
                pred += time.perf_counter() - t0
                payload = {
                    "kind": "adv0116-completion",
                    "load": label,
                    "seq": seq,
                    "writer_id": 0,
                    "predicate_verdict": v_last.verdict,
                }
                t1 = time.perf_counter()
                data = elog.encode_line(payload)
                ser += time.perf_counter() - t1
                t2 = time.perf_counter()
                if log._fd is None:
                    log.open()
                assert log._fd is not None
                elog._write_atomic(log._fd, data)
                app += time.perf_counter() - t2
        wall = time.perf_counter() - wall0
        ru1 = resource.getrusage(resource.RUSAGE_SELF)
        scan = elog.scan(log_path)
        expected = n
        integ = _integrity(scan, expected)
        total = pred + ser + app
        bytes_written = int(scan.get("bytes") or 0)
        return {
            "name": label,
            "n_completions": n,
            "writers": 1,
            "wall_s": round(wall, 6),
            "predicate_s": round(pred, 6),
            "serialize_s": round(ser, 6),
            "append_s": round(app, 6),
            "fsync_s": 0.0,
            "lock_wait_s": 0.0,
            "predicate_frac": round(pred / wall, 6) if wall else 0.0,
            "serialize_frac": round(ser / wall, 6) if wall else 0.0,
            "append_frac": round(app / wall, 6) if wall else 0.0,
            "fsync_frac": 0.0,
            "lock_wait_frac": 0.0,
            "attributed_sum_s": round(total, 6),
            "bytes_written": bytes_written,
            "io": _rusage_delta(ru0, ru1),
            "predicate_verdict": None if v_last is None else v_last.verdict,
            "integrity": integ,
            "production_path": {
                "fsync_in_append": False,
                "fcntl_used": False,
                "mechanism": "O_APPEND single os.write",
            },
        }


def fsync_comparison_arm(n: int = 40) -> dict[str, Any]:
    """Not on the production append path. Measures what per-record fsync would cost."""
    with tempfile.TemporaryDirectory(prefix="adv0116-fsync-") as tmp:
        path = Path(tmp) / "EVENTS.jsonl"
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        if getattr(os, "O_BINARY", 0):
            flags |= os.O_BINARY
        fd = os.open(path, flags, 0o644)
        fsync_s = write_s = 0.0
        try:
            for seq in range(n):
                data = elog.encode_line(
                    {"kind": "adv0116-fsync-arm", "seq": seq, "writer_id": 0}
                )
                t0 = time.perf_counter()
                os.write(fd, data)
                write_s += time.perf_counter() - t0
                t1 = time.perf_counter()
                os.fsync(fd)
                fsync_s += time.perf_counter() - t1
        finally:
            os.close(fd)
        return {
            "n": n,
            "write_s": round(write_s, 6),
            "fsync_s": round(fsync_s, 6),
            "fsync_per_record_us": round((fsync_s / n) * 1e6, 3) if n else 0.0,
            "note": "os.fsync is NOT in EventLog.append; this arm is attribution-only",
        }


def concurrent_fanout(writers: int, per_writer: int, *, atomic: bool) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="adv0116-fan-") as tmp:
        path = Path(tmp) / "EVENTS.jsonl"
        result = elog.run_fanout(
            path, writers=writers, per_writer=per_writer, atomic=atomic
        )
    expected = writers * per_writer
    integ = _integrity(result, expected)
    wall = float(result.get("wall_seconds") or 0.0)
    parsed = int(result.get("parsed") or 0)
    throughput = (parsed / wall) if wall > 0 else 0.0
    return {
        "writers": writers,
        "per_writer": per_writer,
        "expected": expected,
        "atomic": atomic,
        "wall_s": round(wall, 6),
        "throughput_events_per_s": round(throughput, 2),
        "line_count": result.get("line_count"),
        "parsed": parsed,
        "torn": result.get("torn"),
        "unique_writer_seq": result.get("unique_writer_seq"),
        "writer_failures": result.get("writer_failures") or [],
        "all_present": result.get("all_present"),
        "integrity": integ,
        "os_name": result.get("os_name"),
        "mutant_chunk": result.get("mutant_chunk"),
    }
