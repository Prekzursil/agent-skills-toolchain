"""Local equivalent measurements for CNF-0065 cited numbers."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable

JSON_OBJECT = {"zeta": True, "alpha": [1, 2, 3], "mu": {"k": "v"}}
REPS = 11
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def json_wire_size(*, compact: bool) -> int:
    if compact:
        return len(json.dumps(JSON_OBJECT, sort_keys=True, separators=(",", ":")))
    return len(json.dumps(JSON_OBJECT))


def sha256_empty_hex() -> str:
    return hashlib.sha256(b"").hexdigest()


def null_loop_ms(inner: int = 20000) -> float:
    t0 = time.perf_counter()
    acc = 0
    for i in range(inner):
        acc += i & 1
    t1 = time.perf_counter()
    if acc < 0:
        raise RuntimeError("unreachable")
    return (t1 - t0) * 1000.0


def measure_repetitions(fn: Callable[[], Any], n: int = REPS) -> list[Any]:
    return [fn() for _ in range(n)]
