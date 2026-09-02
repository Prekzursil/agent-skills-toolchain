#!/usr/bin/env python3
"""IMP-0224 probe 2: per-line schema check over a kill-loop, plus detector control.

Mechanically different from probe 1: does not use inspect_published_bytes as
the pass predicate. Splits published bytes on newline and schema-checks each
line against a duplicated required-field list. A planted truncated line and a
naive in-place writer must turn the check red.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LEDGER_DIR = REPO / "tools" / "event-ledger"
sys.path.insert(0, str(LEDGER_DIR))

import ledger as L  # noqa: E402

UNIT = "IMP-0224"
KILL_TARGET = LEDGER_DIR / "kill_target.py"
ITERATIONS = 50
PAYLOAD = 65536
CHUNK = 256
TS_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
# Duplicated on purpose: independent of ledger.REQUIRED.
PROBE2_REQUIRED = (
    "kind",
    "seq",
    "ts",
    "actor",
    "unit_id",
    "phase",
    "from_state",
    "to_state",
    "correlation_id",
    "causality_id",
    "payload",
    "prev_sha256",
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def line_schema_errors(obj: object) -> list[str]:
    errs: list[str] = []
    if not isinstance(obj, dict):
        return ["not-object"]
    for key in PROBE2_REQUIRED:
        if key not in obj:
            errs.append(f"missing:{key}")
    if obj.get("kind") != "run-ledger-v1":
        errs.append("kind")
    seq = obj.get("seq")
    if type(seq) is not int or seq < 1:
        errs.append("seq")
    ts = obj.get("ts")
    if not isinstance(ts, str) or not TS_RE.match(ts):
        errs.append("ts")
    for key in (
        "actor",
        "unit_id",
        "phase",
        "from_state",
        "to_state",
        "correlation_id",
        "causality_id",
    ):
        val = obj.get(key)
        if not isinstance(val, str) or not val:
            errs.append(key)
    if not isinstance(obj.get("payload"), dict):
        errs.append("payload")
    prev = obj.get("prev_sha256")
    if not isinstance(prev, str) or not SHA_RE.match(prev):
        errs.append("prev_sha256")
    return errs


def schema_check_bytes(raw: bytes) -> dict:
    """Per-line schema oracle. Does not call ledger.inspect_published_bytes."""
    missing_nl = bool(raw) and not raw.endswith(b"\n")
    text = raw.decode("utf-8", errors="replace")
    if text.endswith("\n"):
        parts = text[:-1].split("\n")
    else:
        parts = text.split("\n") if text else []
    json_fail = 0
    schema_fail = 0
    ok = 0
    for part in parts:
        if part == "":
            json_fail += 1
            continue
        try:
            obj = json.loads(part)
        except json.JSONDecodeError:
            json_fail += 1
            continue
        errs = line_schema_errors(obj)
        if errs:
            schema_fail += 1
        else:
            ok += 1
    half = json_fail + schema_fail + (1 if missing_nl else 0)
    return {
        "missing_trailing_newline": missing_nl,
        "json_fail": json_fail,
        "schema_fail": schema_fail,
        "ok_lines": ok,
        "half_written": half,
        "line_count": len(parts),
    }


def seed(path: Path, tag: str) -> None:
    L.LedgerWriter(path).append(
        actor="probe2",
        unit_id=UNIT,
        phase="7",
        from_state="absent",
        to_state="seeded",
        correlation_id=f"probe2-{tag}",
        causality_id="genesis",
        payload={"seed": True, "tag": tag},
    )


def kill_child(path: Path, mode: str, payload: int, chunk: int, delay_ms: float) -> int:
    proc = subprocess.Popen(
        [
            sys.executable,
            "-B",
            str(KILL_TARGET),
            "--path",
            str(path),
            "--mode",
            mode,
            "--payload-bytes",
            str(payload),
            "--chunk-size",
            str(chunk),
            "--delay-ms",
            str(delay_ms),
        ],
        cwd=str(REPO),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    t0 = time.monotonic()
    before = path.stat().st_size
    while time.monotonic() - t0 < 2.5:
        if mode == "atomic" and L.staging_paths(path.parent):
            break
        if mode == "naive" and path.stat().st_size > before:
            break
        if proc.poll() is not None:
            break
        time.sleep(0.0004)
    if proc.poll() is None:
        time.sleep(0.001 if mode == "atomic" else 0.008)
        try:
            os.kill(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    return proc.returncode if proc.returncode is not None else -9


def atomic_loop() -> dict:
    json_fail = 0
    schema_fail = 0
    missing_nl = 0
    ok_lines = 0
    ledgers = 0
    for i in range(ITERATIONS):
        tmp = tempfile.mkdtemp(prefix="imp0224-p2-")
        path = Path(tmp) / "run.jsonl"
        seed(path, f"a{i}")
        kill_child(path, "atomic", PAYLOAD, CHUNK, 0.0)
        raw = path.read_bytes() if path.is_file() else b""
        chk = schema_check_bytes(raw)
        json_fail += chk["json_fail"]
        schema_fail += chk["schema_fail"]
        missing_nl += 1 if chk["missing_trailing_newline"] else 0
        ok_lines += chk["ok_lines"]
        ledgers += 1
        try:
            for p in Path(tmp).iterdir():
                p.unlink()
            Path(tmp).rmdir()
        except OSError:
            pass
    return {
        "ledgers": ledgers,
        "json_fail": json_fail,
        "schema_fail": schema_fail,
        "missing_trailing_newline": missing_nl,
        "ok_lines": ok_lines,
        "half_written": json_fail + schema_fail + missing_nl,
    }


def naive_detector() -> dict:
    hits = 0
    trials = 8
    samples = []
    for i in range(trials):
        tmp = tempfile.mkdtemp(prefix="imp0224-p2n-")
        path = Path(tmp) / "run.jsonl"
        seed(path, f"n{i}")
        kill_child(path, "naive", payload=4096, chunk=16, delay_ms=4.0)
        raw = path.read_bytes() if path.is_file() else b""
        chk = schema_check_bytes(raw)
        torn = (
            chk["missing_trailing_newline"]
            or chk["json_fail"] > 0
            or chk["schema_fail"] > 0
        )
        if torn:
            hits += 1
        samples.append(
            {
                "torn": torn,
                "missing_nl": chk["missing_trailing_newline"],
                "json_fail": chk["json_fail"],
                "bytes": len(raw),
            }
        )
        try:
            for p in Path(tmp).iterdir():
                p.unlink()
            Path(tmp).rmdir()
        except OSError:
            pass
    return {"trials": trials, "torn_hits": hits, "samples": samples}


def planted_control() -> dict:
    with tempfile.TemporaryDirectory(prefix="imp0224-p2p-") as td:
        path = Path(td) / "run.jsonl"
        seed(path, "plant")
        good = schema_check_bytes(path.read_bytes())
        torn_bytes = path.read_bytes() + b'{"kind":"run-ledger-v1","seq":2'
        bad = schema_check_bytes(torn_bytes)
    return {
        "good_half": good["half_written"],
        "bad_half": bad["half_written"],
        "fired_on_bad": bad["half_written"] > 0,
        "silent_on_good": good["half_written"] == 0,
    }


def main() -> int:
    loop = atomic_loop()
    plant = planted_control()
    naive = naive_detector()
    out = {
        "unit_id": UNIT,
        "probe": "probe2-line-schema",
        "atomic_kill_loop": loop,
        "planted_truncation": plant,
        "naive_in_place_kill": naive,
        "pass": (
            loop["ledgers"] == ITERATIONS
            and loop["half_written"] == 0
            and plant["fired_on_bad"]
            and plant["silent_on_good"]
            and naive["torn_hits"] >= 1
        ),
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"schema_half={loop['half_written']} planted_bad={plant['fired_on_bad']} "
        f"naive_torn={naive['torn_hits']}/{naive['trials']}"
    )
    if loop["ledgers"] != ITERATIONS:
        return fail(f"ledgers {loop['ledgers']}/{ITERATIONS}")
    if loop["half_written"] != 0:
        return fail(f"half_written={loop['half_written']}")
    if not plant["fired_on_bad"] or not plant["silent_on_good"]:
        return fail(f"planted control {plant}")
    if naive["torn_hits"] < 1:
        return fail(f"naive detector did not fire {naive['samples']}")
    print(
        f"SUCCESS:{UNIT}-probe2 per-line schema 0 half-written; "
        "naive/planted controls fire"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
