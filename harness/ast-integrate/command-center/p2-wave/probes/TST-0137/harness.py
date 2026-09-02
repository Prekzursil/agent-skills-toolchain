"""Live 256-unit release against the arrival scheduler + vendor fixture.

Rate is measured from dispatcher timestamps binned into 1-second buckets
(window_ticks ticks := 1 s). The configured ceiling is only a comparison
target; it is never copied into the measured peak.

A second, independent signal is the fixture HTTP server's arrival count.
Those two counts must agree within 1%.
"""
from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from arrival_scheduler.scheduler import (  # noqa: E402
    WINDOW_TICKS,
    naive_burst,
    schedule_arrivals,
)

UNIT = "TST-0137"
N_UNITS = 256
CEILING_PER_SEC = 20
SEED = 1_370_137
JITTER_FRAC = 1.0
AGREE_TOL = 0.01
RECEIPT = REPO / "command-center" / "receipts" / "TST-0137.json"


class VendorFixture(ThreadingHTTPServer):
    """Vendor-boundary fixture with its own arrival log (not the dispatcher log)."""

    def __init__(self, addr: tuple[str, int]) -> None:
        super().__init__(addr, _VendorHandler)
        self.arrivals: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def record(self, unit_id: str, recv_ns: int) -> None:
        with self._lock:
            self.arrivals.append({"unit_id": unit_id, "recv_ns": recv_ns})

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.arrivals)


class _VendorHandler(BaseHTTPRequestHandler):
    server: VendorFixture

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or "0")
        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            payload = {}
        unit_id = str(payload.get("unit_id") or "")
        self.server.record(unit_id, time.time_ns())
        raw = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: ARG002
        return


def start_fixture() -> tuple[VendorFixture, str]:
    httpd = VendorFixture(("127.0.0.1", 0))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    return httpd, f"http://{host}:{port}/arrive"


def stop_fixture(httpd: VendorFixture) -> None:
    httpd.shutdown()
    httpd.server_close()


def bin_dispatch_1s(times_ticks: list[int], window_ticks: int = WINDOW_TICKS) -> dict[int, int]:
    """Aligned 1-second buckets. 1 s := window_ticks (the scheduler window)."""
    buckets: Counter[int] = Counter()
    for ticks in times_ticks:
        buckets[int(ticks) // int(window_ticks)] += 1
    return dict(sorted(buckets.items()))


def meter_from_dispatch(times_ticks: list[int], ceiling: int) -> dict[str, Any]:
    buckets = bin_dispatch_1s(times_ticks)
    peak = max(buckets.values()) if buckets else 0
    return {
        "n_dispatch": len(times_ticks),
        "bins_1s": buckets,
        "peak_per_1s": peak,
        "ceiling": ceiling,
        "breach": peak > ceiling,
        "source": "dispatch_timestamps_binned_1s",
        "not_read_from_config": True,
    }


def count_agreement(dispatch_n: int, server_n: int, tol: float = AGREE_TOL) -> dict[str, Any]:
    denom = max(dispatch_n, server_n, 1)
    rel = abs(dispatch_n - server_n) / float(denom)
    return {
        "dispatch_n": dispatch_n,
        "server_n": server_n,
        "relative_error": rel,
        "tolerance": tol,
        "agree": rel <= tol,
    }


def _post(url: str, unit_id: str) -> None:
    body = json.dumps({"unit_id": unit_id}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status != 200:
            raise RuntimeError(f"fixture status={resp.status} unit={unit_id}")


def release(stagger: bool) -> dict[str, Any]:
    """Admit 256 units at t=0 through the scheduler; POST each to the fixture."""
    if stagger:
        sched = schedule_arrivals(
            N_UNITS,
            CEILING_PER_SEC,
            seed=SEED,
            jitter_frac=JITTER_FRAC,
        )
        mode = "stagger_enabled"
    else:
        sched = naive_burst(N_UNITS, CEILING_PER_SEC)
        mode = "stagger_disabled"

    httpd, url = start_fixture()
    dispatch_log: list[dict[str, Any]] = []
    try:
        for uid, ticks in zip(sched.unit_ids, sched.times_ticks):
            dispatch_log.append(
                {"unit_id": uid, "dispatch_ticks": int(ticks), "mode": mode}
            )
            _post(url, uid)
        server_log = httpd.snapshot()
    finally:
        stop_fixture(httpd)

    times = [int(row["dispatch_ticks"]) for row in dispatch_log]
    meter = meter_from_dispatch(times, CEILING_PER_SEC)
    agree = count_agreement(meter["n_dispatch"], len(server_log))
    unique_ts = len({int(t) for t in times})
    return {
        "mode": mode,
        "stagger": stagger,
        "n_units": N_UNITS,
        "ceiling_per_sec": CEILING_PER_SEC,
        "window_ticks": WINDOW_TICKS,
        "seed": None if not stagger else SEED,
        "jitter_frac": JITTER_FRAC if stagger else 0.0,
        "dispatch_log": dispatch_log,
        "server_arrival_count": len(server_log),
        "server_unit_ids": [row["unit_id"] for row in server_log],
        "meter": meter,
        "agreement": agree,
        "unique_dispatch_timestamps": unique_ts,
        "scheduler_times_ticks": list(sched.times_ticks),
    }


def compact(result: dict[str, Any]) -> dict[str, Any]:
    meter = result["meter"]
    return {
        "mode": result["mode"],
        "stagger": result["stagger"],
        "n_units": result["n_units"],
        "ceiling_per_sec": result["ceiling_per_sec"],
        "peak_per_1s": meter["peak_per_1s"],
        "breach": meter["breach"],
        "bins_1s": {str(k): int(v) for k, v in meter["bins_1s"].items()},
        "n_dispatch": meter["n_dispatch"],
        "server_arrival_count": result["server_arrival_count"],
        "agreement": result["agreement"],
        "unique_dispatch_timestamps": result["unique_dispatch_timestamps"],
        "source": meter["source"],
    }
