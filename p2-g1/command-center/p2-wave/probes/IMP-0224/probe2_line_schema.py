"""IMP-0224 probe 2: zero half-written records, by independent per-line schema check.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0224/probe2_line_schema.py
Runs its own 50-iteration kill loop, then schema-checks every published line with an
INDEPENDENT required-field list (never ledger.inspect_published_bytes as the pass
predicate). Two adversarial controls: a planted truncated tail fires the detector, and a
naive in-place chunked writer (mutation: replace-atomic-rename-with-direct-write) produces
torn tails the schema check catches.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

W = Path(__file__).resolve().parents[4]
KILL_TARGET = W / "tools" / "event-ledger" / "kill_target.py"
NAIVE_WRITER = Path(__file__).resolve().parent / "naive_writer.py"

REQUIRED_FIELDS = ("kind", "unit_id", "phase")


def line_schema_check(raw: bytes) -> dict:
    """Independent per-line JSON + required-field check."""
    text = raw.decode("utf-8", errors="replace")
    ok_lines = 0
    json_fail = 0
    schema_fail = 0
    half_written = 0
    lines = text.splitlines()
    for ln in lines:
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            json_fail += 1
            half_written += 1
            continue
        if not isinstance(obj, dict) or any(not obj.get(f) for f in REQUIRED_FIELDS):
            schema_fail += 1
            continue
        ok_lines += 1
    missing_nl = bool(lines) and not text.endswith("\n")
    if missing_nl:
        half_written += 1
    return {
        "ok_lines": ok_lines,
        "json_fail": json_fail,
        "schema_fail": schema_fail,
        "half_written": half_written,
        "missing_trailing_newline": missing_nl,
    }


def payload_schema_check(raw: bytes) -> dict:
    """Schema check tolerant of seed lines (text field, no phase)."""
    text = raw.decode("utf-8", errors="replace")
    json_fail = 0
    half = 0
    schema_fail = 0
    for ln in text.splitlines():
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            json_fail += 1
            half += 1
            continue
        if not isinstance(obj, dict) or not obj.get("unit_id") or not obj.get("phase"):
            schema_fail += 1
    return {"json_fail": json_fail, "half_written": half, "schema_fail": schema_fail}


def run_kill_iteration(root: Path, i: int) -> bytes:
    dest = root / ("schema-%03d.jsonl" % i)
    seed = {"seq": 1, "ts": "2026-10-25T00:00:00", "kind": "note",
            "unit_id": "seed", "phase": "7", "text": "seed"}
    dest.write_text(json.dumps(seed) + "\n", encoding="utf-8")
    staging = dest.with_name(dest.name + ".staging")
    proc = subprocess.Popen(
        [
            sys.executable, "-B", str(KILL_TARGET),
            "--path", str(dest),
            "--payload-bytes", "2048",
            "--chunk-size", "128",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            if staging.exists() and staging.stat().st_size > 0:
                break
        except OSError:
            pass
        time.sleep(0.002)
    if proc.poll() is None:
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except OSError:
            pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    return dest.read_bytes() if dest.exists() else b""


def run_naive_trial(root: Path, i: int) -> dict:
    dest = root / ("naive-%03d.jsonl" % i)
    seed = {"seq": 1, "ts": "2026-10-25T00:00:00", "kind": "note",
            "unit_id": "seed", "phase": "7", "text": "seed"}
    dest.write_text(json.dumps(seed) + "\n", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable, "-B", str(NAIVE_WRITER),
            "--path", str(dest),
            "--payload-bytes", "4096",
            "--chunk-size", "96",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    seed_len = len(json.dumps(seed)) + 2
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            if dest.stat().st_size > seed_len:
                break
        except OSError:
            pass
        time.sleep(0.002)
    if proc.poll() is None:
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except OSError:
            pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    raw = dest.read_bytes()
    chk = payload_schema_check(raw)
    return {"trial": i, "bytes": len(raw), "torn": chk["half_written"] > 0,
            "json_fail": chk["json_fail"], "schema_fail": chk["schema_fail"]}


def main() -> int:
    iterations = 50
    with tempfile.TemporaryDirectory(prefix="imp0224-schema-") as td:
        root = Path(td)
        ledgers = 0
        ok_lines_total = 0
        half_written = 0
        json_fail_total = 0
        schema_fail_total = 0
        missing_nl_total = 0
        for i in range(iterations):
            raw = run_kill_iteration(root, i)
            chk = line_schema_check(raw)
            ledgers += 1
            ok_lines_total += chk["ok_lines"]
            half_written += chk["half_written"]
            json_fail_total += chk["json_fail"]
            schema_fail_total += chk["schema_fail"]
            missing_nl_total += 1 if chk["missing_trailing_newline"] else 0

        # Adversarial control 1: planted truncated tail on a complete ledger.
        good_dest = root / "planted.jsonl"
        good_lines = []
        for n in range(3):
            good_lines.append(json.dumps(
                {"seq": n, "ts": "2026-10-25T00:00:0%d" % n, "kind": "note",
                 "unit_id": "u%d" % n, "phase": "7", "text": "ok"}))
        good_dest.write_text("\n".join(good_lines) + "\n", encoding="utf-8")
        good_chk = line_schema_check(good_dest.read_bytes())
        bad_dest = root / "planted-bad.jsonl"
        bad_dest.write_bytes(good_dest.read_bytes() + b'{"trunc')
        bad_chk = line_schema_check(bad_dest.read_bytes())

        # Adversarial control 2: naive in-place chunked writer, killed mid-write.
        naive_trials = 8
        naive_samples = []
        torn_hits = 0
        for i in range(naive_trials):
            row = run_naive_trial(root, i)
            naive_samples.append(row)
            if row["torn"]:
                torn_hits += 1

    doc = {
        "unit_id": "IMP-0224",
        "probe": "probe2-line-schema",
        "atomic_kill_loop": {
            "ledgers": ledgers,
            "ok_lines": ok_lines_total,
            "json_fail": json_fail_total,
            "schema_fail": schema_fail_total,
            "half_written": half_written,
            "missing_trailing_newline": missing_nl_total,
        },
        "planted_truncation": {
            "good_half": good_chk["half_written"],
            "silent_on_good": good_chk["half_written"] == 0,
            "bad_half": bad_chk["half_written"],
            "fired_on_bad": bad_chk["half_written"] > 0,
        },
        "naive_in_place_kill": {
            "trials": naive_trials,
            "torn_hits": torn_hits,
            "samples": naive_samples[:3],
        },
        "pass": (
            ledgers == iterations
            and half_written == 0
            and json_fail_total == 0
            and schema_fail_total == 0
            and missing_nl_total == 0
            and good_chk["half_written"] == 0
            and bad_chk["half_written"] > 0
            and torn_hits >= naive_trials - 1
        ),
    }
    out = Path(__file__).resolve().parent / "probe2-schema.raw.json"
    out.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    print("schema_half=%d planted_bad=%s naive_torn=%d/%d"
          % (half_written, doc["planted_truncation"]["fired_on_bad"], torn_hits, naive_trials))
    if doc["pass"]:
        print("SUCCESS:IMP-0224-probe2 per-line schema zero half-written; planted and"
              " naive controls fire")
        return 0
    print("FAILED:IMP-0224-probe2 schema or adversarial control failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
