#!/usr/bin/env python3
"""TST-0174 concurrent-writer integrity harness."""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import shutil
import tempfile
import time
from pathlib import Path

from atomic_cache import (
    ABSENT,
    COMPLETE,
    PARTIAL,
    atomic_publish,
    classify_bytes,
    classify_path,
    encode,
    leftover_tmps,
    write_worker,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0174"
TRIALS = 1000
ATOMIC_PAYLOAD = 48 * 1024
MUTANT_PAYLOAD = 64 * 1024

PRODUCTION_CANDIDATES = [
    "platform/plugin/cache.py",
    "platform/plugin/fsops.py",
    "tools/agentspec/agentspec/artifact_cache.py",
    "tools/agentspec/agentspec/cache.py",
    "tools/agentspec/agentspec/determinism.py",
    "tools/plugin-cache-reaper/reap.py",
    "tools/plugin/cache.py",
    "platform/cache/artifact_cache.py",
    "tools/cache/atomic_cache.py",
]


def production_census() -> dict:
    rows = []
    for rel in PRODUCTION_CANDIDATES:
        path = REPO / rel
        rows.append({"path": rel, "present": path.is_file()})
    return {
        "present": any(r["present"] for r in rows),
        "candidates": rows,
        "measured_layer": "command-center/p2-wave/probes/TST-0174/atomic_cache.py",
        "publish": "tmp-plus-os.replace",
    }


def _payload(tag: bytes, size: int, nonce: bytes) -> bytes:
    body = tag + nonce + (tag[:1] * max(0, size - len(tag) - len(nonce)))
    return encode(body[:size] if len(body) > size else body.ljust(size, tag[:1]))


def _reader_main(path: str, stop_path: str, result_path: str) -> None:
    dest = Path(path)
    stop = Path(stop_path)
    counts = {COMPLETE: 0, PARTIAL: 0, ABSENT: 0, "ERROR": 0}
    reasons: list[str] = []
    reads = 0
    while True:
        status, reason = classify_path(dest)
        counts[status] = counts.get(status, 0) + 1
        reads += 1
        if status == PARTIAL and reason and len(reasons) < 12:
            reasons.append(str(reason))
        if stop.exists():
            status, reason = classify_path(dest)
            counts[status] = counts.get(status, 0) + 1
            reads += 1
            if status == PARTIAL and reason and len(reasons) < 12:
                reasons.append(str(reason))
            break
    Path(result_path).write_text(
        json.dumps({"counts": counts, "partial_reasons": reasons, "reads": reads}),
        encoding="utf-8",
    )


def _load_reader(result_path: Path) -> dict:
    if not result_path.is_file():
        return {"counts": {}, "partial_reasons": [], "reads": 0}
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"counts": {}, "partial_reasons": ["reader-unparseable"], "reads": 0}
    if not isinstance(data, dict):
        return {"counts": {}, "partial_reasons": [], "reads": 0}
    return data


def run_one_trial(
    *,
    mode: str,
    payload_a: bytes,
    payload_b: bytes,
    payload_old: bytes,
    digest_a: str,
    digest_b: str,
    digest_old: str,
    ctx: mp.context.BaseContext,
) -> dict:
    root = Path(tempfile.mkdtemp(prefix="tst0174-"))
    dest = root / "same-key"
    stop_path = root / "stop"
    result_path = root / "reader.json"
    try:
        atomic_publish(dest, payload_old)
        reader = ctx.Process(
            target=_reader_main,
            args=(str(dest), str(stop_path), str(result_path)),
        )
        w1 = ctx.Process(target=write_worker, args=(str(dest), payload_a, mode))
        w2 = ctx.Process(target=write_worker, args=(str(dest), payload_b, mode))
        reader.start()
        time.sleep(0.002)
        w1.start()
        w2.start()
        w1.join(30)
        w2.join(30)
        alive = []
        if w1.is_alive():
            w1.terminate()
            alive.append("w1")
        if w2.is_alive():
            w2.terminate()
            alive.append("w2")
        stop_path.write_bytes(b"1")
        reader.join(10)
        if reader.is_alive():
            reader.terminate()
            alive.append("reader")
        observed = _load_reader(result_path)
        final_status, final_reason = classify_path(dest)
        leftovers = leftover_tmps(root)
        winner = None
        if final_status == COMPLETE:
            if final_reason == digest_a:
                winner = "A"
            elif final_reason == digest_b:
                winner = "B"
            elif final_reason == digest_old:
                winner = "OLD"
            else:
                winner = "UNKNOWN"
        return {
            "mode": mode,
            "final_status": final_status,
            "final_reason": final_reason,
            "winner": winner,
            "w1_exit": w1.exitcode,
            "w2_exit": w2.exitcode,
            "reader_exit": reader.exitcode,
            "alive_after_join": alive,
            "leftover_tmps": leftovers,
            "partial_reads": int((observed.get("counts") or {}).get(PARTIAL) or 0),
            "complete_reads": int((observed.get("counts") or {}).get(COMPLETE) or 0),
            "absent_reads": int((observed.get("counts") or {}).get(ABSENT) or 0),
            "reader_reads": int(observed.get("reads") or 0),
            "partial_reasons": list(observed.get("partial_reasons") or []),
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run_atomic_property(trials: int = TRIALS) -> dict:
    ctx = mp.get_context("fork")
    nonce_a = os.urandom(16)
    nonce_b = os.urandom(16)
    nonce_old = os.urandom(16)
    payload_a = _payload(b"AAA", ATOMIC_PAYLOAD, nonce_a)
    payload_b = _payload(b"BBB", ATOMIC_PAYLOAD, nonce_b)
    payload_old = _payload(b"OLD", ATOMIC_PAYLOAD, nonce_old)
    digest_a = classify_bytes(payload_a)[1]
    digest_b = classify_bytes(payload_b)[1]
    digest_old = classify_bytes(payload_old)[1]
    winners = {"A": 0, "B": 0, "OLD": 0, "UNKNOWN": 0, None: 0}
    partial_trials = 0
    leftover_trials = 0
    bad: list[dict] = []
    total_partial_reads = 0
    total_reader_reads = 0
    for i in range(trials):
        row = run_one_trial(
            mode="atomic",
            payload_a=payload_a,
            payload_b=payload_b,
            payload_old=payload_old,
            digest_a=str(digest_a),
            digest_b=str(digest_b),
            digest_old=str(digest_old),
            ctx=ctx,
        )
        winners[row["winner"]] = winners.get(row["winner"], 0) + 1
        total_partial_reads += row["partial_reads"]
        total_reader_reads += row["reader_reads"]
        failed = False
        if row["partial_reads"] > 0:
            partial_trials += 1
            failed = True
        if row["leftover_tmps"]:
            leftover_trials += 1
            failed = True
        if row["final_status"] != COMPLETE or row["winner"] not in {"A", "B"}:
            failed = True
        if row["w1_exit"] not in (0, None) or row["w2_exit"] not in (0, None):
            failed = True
        if failed:
            bad.append({"trial": i, **{k: row[k] for k in (
                "final_status",
                "winner",
                "partial_reads",
                "leftover_tmps",
                "w1_exit",
                "w2_exit",
                "partial_reasons",
            )}})
            if len(bad) >= 8:
                break
    ok = (
        len(bad) == 0
        and partial_trials == 0
        and leftover_trials == 0
        and winners.get("A", 0) + winners.get("B", 0) == trials
    )
    return {
        "pass": ok,
        "trials": trials,
        "winners": {str(k): v for k, v in winners.items() if k is not None or v},
        "partial_trials": partial_trials,
        "leftover_trials": leftover_trials,
        "total_partial_reads": total_partial_reads,
        "total_reader_reads": total_reader_reads,
        "failures": bad,
        "measured_layer": "atomic_cache.atomic_publish",
    }


def run_mutation_control(trials: int = 4) -> dict:
    ctx = mp.get_context("fork")
    payload_a = _payload(b"AAA", MUTANT_PAYLOAD, os.urandom(16))
    payload_b = _payload(b"BBB", MUTANT_PAYLOAD, os.urandom(16))
    payload_old = _payload(b"OLD", MUTANT_PAYLOAD, os.urandom(16))
    digest_a = classify_bytes(payload_a)[1]
    digest_b = classify_bytes(payload_b)[1]
    digest_old = classify_bytes(payload_old)[1]
    rows = []
    for _ in range(trials):
        row = run_one_trial(
            mode="inplace",
            payload_a=payload_a,
            payload_b=payload_b,
            payload_old=payload_old,
            digest_a=str(digest_a),
            digest_b=str(digest_b),
            digest_old=str(digest_old),
            ctx=ctx,
        )
        rows.append(row)
        if row["partial_reads"] > 0:
            break
    partial_seen = sum(r["partial_reads"] for r in rows)
    detector_red = partial_seen > 0
    return {
        "pass": detector_red,
        "trials_run": len(rows),
        "partial_reads": partial_seen,
        "partial_reasons": rows[-1]["partial_reasons"] if rows else [],
        "known_broken": "inplace_publish (atomic replace removed)",
        "detector_red": detector_red,
        "last_final_status": rows[-1]["final_status"] if rows else None,
    }


def run_leftover_inspection() -> dict:
    ctx = mp.get_context("fork")
    payload_a = _payload(b"AAA", ATOMIC_PAYLOAD, os.urandom(16))
    payload_b = _payload(b"BBB", ATOMIC_PAYLOAD, os.urandom(16))
    payload_old = _payload(b"OLD", ATOMIC_PAYLOAD, os.urandom(16))
    row = run_one_trial(
        mode="atomic",
        payload_a=payload_a,
        payload_b=payload_b,
        payload_old=payload_old,
        digest_a=str(classify_bytes(payload_a)[1]),
        digest_b=str(classify_bytes(payload_b)[1]),
        digest_old=str(classify_bytes(payload_old)[1]),
        ctx=ctx,
    )
    leftovers = list(row["leftover_tmps"])
    return {
        "pass": leftovers == [] and row["final_status"] == COMPLETE,
        "leftover_tmps": leftovers,
        "final_status": row["final_status"],
        "winner": row["winner"],
        "signal": "directory scan after concurrent atomic publish",
    }
