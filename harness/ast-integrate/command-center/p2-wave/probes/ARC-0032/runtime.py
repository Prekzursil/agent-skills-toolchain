#!/usr/bin/env python3
"""Measured analogue of the A5 local substrate: JSONL ledger + subprocess dispatch + harvest.

This is not ARC-0031 DESIGN.json (absent on this tree). It is a runnable stand-in of
the catalog contract: typed queue, append-only ledger with a claim/dedupe key,
local dispatcher, harvest, one completion reducer. Worktree and cloud dispatch
are not implemented here.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLOB = b"ARC-0032" * 512
COMPUTE_ROUNDS = 12000
EVENTS_PER_UNIT = 5  # enqueue, claim, running, harvest, complete


def utc_ms() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def unit_id(i: int) -> str:
    return f"U{i:04d}"


def _last_line(fh) -> str:
    fh.seek(0, os.SEEK_END)
    pos = fh.tell()
    if pos == 0:
        return ""
    buf = b""
    while pos > 0:
        take = min(512, pos)
        pos -= take
        fh.seek(pos)
        buf = fh.read(take) + buf
        if buf.count(b"\n") >= 2 or pos == 0:
            break
    lines = [ln for ln in buf.splitlines() if ln.strip()]
    return lines[-1].decode("utf-8") if lines else ""


def append_record(ledger: Path, rec: dict) -> dict:
    rec = dict(rec)
    rec["ts"] = utc_ms()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    if not ledger.exists():
        ledger.touch()
    with ledger.open("rb+") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        last = _last_line(fh)
        if last:
            prev_obj = json.loads(last)
            seq = int(prev_obj["seq"]) + 1
            prev = hashlib.sha256(last.encode("utf-8")).hexdigest()
        else:
            seq = 1
            prev = "0" * 64
        rec["seq"] = seq
        rec["prev"] = prev
        line = json.dumps(rec, separators=(",", ":"), sort_keys=True)
        raw = (line + "\n").encode("utf-8")
        fh.seek(0, os.SEEK_END)
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    rec["_line_bytes"] = len(raw)
    return rec


def burn() -> str:
    h = hashlib.sha256()
    for i in range(COMPUTE_ROUNDS):
        h.update(BLOB)
        h.update(i.to_bytes(4, "little"))
    return h.hexdigest()


def worker_main(unit: str, ledger: Path, artifact: Path, t0_ns: int) -> None:
    ready_ns = time.perf_counter_ns()
    append_record(
        ledger,
        {
            "event": "running",
            "unit_id": unit,
            "dispatch_overhead_ns": ready_ns - t0_ns,
        },
    )
    digest = burn()
    artifact.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "unit_id": unit,
        "digest": digest,
        "sentinel": f"SUCCESS:{unit}",
    }
    artifact.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"unit_id": unit, "ready_ns": ready_ns, "t0_ns": t0_ns}))


def run_one(repo_py: Path, work: Path, unit: str) -> dict:
    ledger = work / "ledger.jsonl"
    artifact = work / "artifacts" / f"{unit}.json"
    t0 = time.perf_counter_ns()
    append_record(ledger, {"event": "claim", "unit_id": unit, "dedupe_key": unit})
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        [
            sys.executable,
            "-B",
            str(repo_py),
            "worker",
            "--unit",
            unit,
            "--ledger",
            str(ledger),
            "--artifact",
            str(artifact),
            "--t0-ns",
            str(t0),
        ],
        cwd=str(HERE.parents[3]),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    wait_ns = time.perf_counter_ns() - t0
    if p.returncode != 0:
        raise RuntimeError(f"worker {unit} rc={p.returncode} err={(p.stderr or '')[-500:]}")
    overhead_ns = None
    for line in (p.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{") and "ready_ns" in line:
            msg = json.loads(line)
            overhead_ns = int(msg["ready_ns"]) - int(msg["t0_ns"])
            break
    return {
        "unit_id": unit,
        "wait_ns": wait_ns,
        "dispatch_overhead_ns": overhead_ns,
        "artifact": str(artifact),
        "rc": p.returncode,
    }


def harvest_one(work: Path, unit: str) -> dict:
    src = work / "artifacts" / f"{unit}.json"
    dst = work / "harvest" / f"{unit}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter_ns()
    dst.write_bytes(src.read_bytes())
    dt = time.perf_counter_ns() - t0
    append_record(
        work / "ledger.jsonl",
        {"event": "harvest", "unit_id": unit, "harvest_ns": dt, "bytes": dst.stat().st_size},
    )
    append_record(
        work / "ledger.jsonl",
        {"event": "complete", "unit_id": unit, "artifact": str(dst.relative_to(work))},
    )
    return {"unit_id": unit, "harvest_ns": dt, "bytes": dst.stat().st_size}


def reduce_complete(work: Path, n: int) -> dict:
    ledger = work / "ledger.jsonl"
    counts: dict[str, int] = {}
    lines = 0
    for raw in ledger.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        rec = json.loads(raw)
        counts[rec["event"]] = counts.get(rec["event"], 0) + 1
        lines += 1
    harvested = list((work / "harvest").glob("U*.json"))
    ok = (
        counts.get("complete", 0) == n
        and counts.get("claim", 0) == n
        and len(harvested) == n
    )
    return {"ok": ok, "counts": counts, "lines": lines, "harvested": len(harvested)}


def run_batch(n: int, concurrency: int, work: Path) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    ledger = work / "ledger.jsonl"
    if ledger.exists():
        ledger.unlink()
    py = HERE / "runtime.py"
    units = [unit_id(i) for i in range(1, n + 1)]
    t_all = time.perf_counter_ns()

    t_enq = time.perf_counter_ns()
    for u in units:
        append_record(ledger, {"event": "enqueue", "unit_id": u})
    enqueue_ns = time.perf_counter_ns() - t_enq

    t_run = time.perf_counter_ns()
    results = []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futs = [pool.submit(run_one, py, work, u) for u in units]
        for fut in as_completed(futs):
            results.append(fut.result())
    run_ns = time.perf_counter_ns() - t_run

    t_h = time.perf_counter_ns()
    harvests = [harvest_one(work, u) for u in units]
    harvest_ns = time.perf_counter_ns() - t_h

    wall_ns = time.perf_counter_ns() - t_all
    red = reduce_complete(work, n)
    if not red["ok"]:
        raise RuntimeError(f"reducer failed {red}")

    size_py = ledger.stat().st_size
    wc = subprocess.run(["wc", "-c", str(ledger)], capture_output=True, text=True, check=True)
    size_wc = int(wc.stdout.split()[0])
    overheads = [r["dispatch_overhead_ns"] for r in results if r.get("dispatch_overhead_ns") is not None]
    waits = [r["wait_ns"] for r in results]
    if len(overheads) < n:
        raise RuntimeError(f"missing dispatch overheads {len(overheads)}/{n}")

    return {
        "n": n,
        "concurrency": concurrency,
        "wall_ns": wall_ns,
        "enqueue_ns": enqueue_ns,
        "run_ns": run_ns,
        "harvest_ns": harvest_ns,
        "ledger_bytes_python": size_py,
        "ledger_bytes_wc": size_wc,
        "ledger_bytes_per_unit_python": size_py / n,
        "ledger_bytes_per_unit_wc": size_wc / n,
        "dispatch_overhead_ns_mean": sum(overheads) / len(overheads),
        "dispatch_overhead_ns_min": min(overheads),
        "dispatch_overhead_ns_max": max(overheads),
        "dispatch_count": len(overheads),
        "service_wait_ns_mean": sum(waits) / len(waits),
        "harvest_ns_mean": sum(h["harvest_ns"] for h in harvests) / len(harvests),
        "reducer": red,
        "events_per_unit": EVENTS_PER_UNIT,
        "ledger_path": str(ledger),
    }


def predict_wall_ns(n: int, c: int, coeff: dict) -> float:
    """T(n,c) = n*t_enq_per + ceil(n/c)*(t_disp+t_svc_net) + n*t_harvest_per + F

    t_svc_net is mean worker wait minus dispatch overhead (compute + worker ledger write).
    """
    import math

    c = max(1, int(c))
    waves = math.ceil(n / c)
    return (
        float(coeff["F_ns"])
        + n * float(coeff["enqueue_ns_per_unit"])
        + waves * float(coeff["wave_ns"])
        + n * float(coeff["harvest_ns_per_unit"])
    )


def fit_coefficients(component: dict) -> dict:
    """Component model from a serial (c=1) calibration batch plus mean overheads."""
    n = int(component["n"])
    # Per-unit enqueue from the serial enqueue loop.
    enq = component["enqueue_ns"] / n
    harvest = component["harvest_ns"] / n
    disp = component["dispatch_overhead_ns_mean"]
    # Mean in-worker+wait time attributed to one occupancy slot.
    wave = component["service_wait_ns_mean"]
    # Fixed term: whatever is left on the c=1 wall after the component sum.
    pred_no_f = n * enq + n * wave + n * harvest
    f = component["wall_ns"] - pred_no_f
    return {
        "form": "T(n,c)=F + n*t_enqueue + ceil(n/c)*t_wave + n*t_harvest",
        "F_ns": f,
        "enqueue_ns_per_unit": enq,
        "wave_ns": wave,
        "harvest_ns_per_unit": harvest,
        "dispatch_overhead_ns_per_unit": disp,
        "calibrated_on": {"n": n, "concurrency": component["concurrency"]},
    }


def parse_supervisor_launches(path: Path) -> dict:
    if not path.is_file():
        return {"verdict": "NOT-CHECKED", "reason": f"missing {path}", "n": 0}
    stamps = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if " LAUNCH " not in line:
            continue
        ts = line.split(" ", 1)[0]
        try:
            dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        stamps.append(dt.timestamp())
    if len(stamps) < 2:
        return {"verdict": "NOT-CHECKED", "reason": "fewer than 2 LAUNCH lines", "n": len(stamps)}
    stamps.sort()
    deltas = [stamps[i] - stamps[i - 1] for i in range(1, len(stamps))]
    deltas.sort()
    mid = deltas[len(deltas) // 2]
    return {
        "verdict": "CONFIRMED",
        "n": len(stamps),
        "first_ts": datetime.fromtimestamp(stamps[0], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_ts": datetime.fromtimestamp(stamps[-1], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "median_inter_launch_s": mid,
        "mean_inter_launch_s": sum(deltas) / len(deltas),
        "min_inter_launch_s": deltas[0],
        "max_inter_launch_s": deltas[-1],
        "observation_window": {
            "start": datetime.fromtimestamp(stamps[0], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": datetime.fromtimestamp(stamps[-1], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }


def _is_http_429_line(line: str) -> bool:
    """True only for rate-limit events, not a bare '429' digit run in hashes or counters."""
    import re

    low = line.lower()
    if "retry-after" in low or "too many requests" in low:
        return True
    if "rate-limit" in low or "rate limit" in low:
        return True
    if re.search(r"(?:status|http(?:/\d+\.\d+)?|code)[^\d]{0,12}429\b", low):
        return True
    if re.search(r"\b429\b", low) and ("throttl" in low or "http" in low):
        return True
    return False


def scan_429(paths: list[Path]) -> dict:
    hits = []
    scanned = 0
    bytes_scanned = 0
    for p in paths:
        if not p.is_file():
            continue
        scanned += 1
        raw = p.read_bytes()
        bytes_scanned += len(raw)
        text = raw.decode("utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if _is_http_429_line(line):
                hits.append({"path": str(p), "line": i, "snippet": line[:180]})
    return {
        "files_scanned": scanned,
        "bytes_scanned": bytes_scanned,
        "hit_count": len(hits),
        "hits_head": hits[:8],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("worker")
    w.add_argument("--unit", required=True)
    w.add_argument("--ledger", required=True)
    w.add_argument("--artifact", required=True)
    w.add_argument("--t0-ns", required=True, type=int)
    r = sub.add_parser("run")
    r.add_argument("--n", type=int, required=True)
    r.add_argument("--concurrency", type=int, required=True)
    r.add_argument("--work", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "worker":
        worker_main(args.unit, Path(args.ledger), Path(args.artifact), args.t0_ns)
        return 0
    summary = run_batch(args.n, args.concurrency, Path(args.work))
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
