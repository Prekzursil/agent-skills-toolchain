#!/usr/bin/env python3
"""Run one census cell: ordered planted tests under one axis tuple."""
from __future__ import annotations

import json
import os
import random
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import suite  # noqa: E402
from common import shuffled_order  # noqa: E402

TESTS = {
    "test_hermetic": suite.test_hermetic,
    "test_order_write": suite.test_order_write,
    "test_order_read": suite.test_order_read,
    "test_tz_utc_offset": suite.test_tz_utc_offset,
    "test_cwd_marker": suite.test_cwd_marker,
    "test_cache_hit": suite.test_cache_hit,
    "test_prng_draw": suite.test_prng_draw,
    "test_undeclared_fetch": suite.test_undeclared_fetch,
}


def run_cell() -> dict:
    if os.environ.get("BLD0044_EGRESS_GUARD") == "1":
        # Windows-adapted egress block (both-states proven by block_control):
        # every connect attempt raises for the duration of this cell.
        import socket as _socket

        class _BlockedSocket(_socket.socket):
            def connect(self, address):
                raise OSError("BLD-0044 egress guard: connect blocked")

        _socket.socket = _BlockedSocket

        def _blocked_create_connection(*a, **k):
            raise OSError("BLD-0044 egress guard: connect blocked")

        _socket.create_connection = _blocked_create_connection
    spec = json.loads(sys.argv[1])
    order_seed = int(spec["order_seed"])
    prng_seed = int(spec["prng_seed"])
    os.environ["TZ"] = str(spec["tz"])
    if hasattr(time, "tzset"):
        time.tzset()
    # Windows repair 2026-10-24: time.tzset() is POSIX-only and its absence
    # crashed the harness before any planted test ran. On Windows the child's
    # local zone comes from the OS, not the TZ env var; the tz axis outcome is
    # recorded honestly by test_tz_utc_offset in each cell (a local-zone
    # mismatch shows up as a FAIL there, which is census data, not a crash).
    os.chdir(str(spec["cwd"]))
    random.seed(prng_seed)
    os.environ["BLD0044_SCRATCH"] = str(spec["scratch"])
    os.environ["BLD0044_CACHE"] = str(spec["cache_dir"])
    Path(spec["scratch"]).mkdir(parents=True, exist_ok=True)
    Path(spec["cache_dir"]).mkdir(parents=True, exist_ok=True)
    results = {}
    for name in shuffled_order(order_seed):
        fn = TESTS[name]
        try:
            fn()
            results[name] = {"outcome": "PASS", "error": None}
        except Exception as exc:  # noqa: BLE001 — census records the exception
            results[name] = {
                "outcome": "FAIL",
                "error": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc(limit=3),
            }
    print(json.dumps({"results": results}, sort_keys=True))
    return results


if __name__ == "__main__":
    run_cell()
