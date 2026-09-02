#!/usr/bin/env python3
"""Executable baseline-failure suspects for CNF-0020.

Exit 1 (RED) means the failure reproduced on this run.
Exit 0 (GREEN) means it did not.
Never consult prior runs. Each invocation is one trial.
"""
from __future__ import annotations

import os
import secrets
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CRLF_FIXTURE = HERE / "fixtures" / "crlf-control.txt"


def fail() -> int:
    return 1


def ok() -> int:
    return 0


def f_crlf_artefact() -> int:
    data = CRLF_FIXTURE.read_bytes()
    return fail() if b"\r\n" in data else ok()


def f_coin_p30() -> int:
    return fail() if secrets.randbelow(10) < 3 else ok()


def f_race_counter() -> int:
    n_threads = int(os.environ.get("CNF0020_CONCURRENCY", "8"))
    n_iter = 200
    counter = 0
    lock_free = True

    def worker() -> None:
        nonlocal counter
        for _ in range(n_iter):
            if lock_free:
                cur = counter
                time.sleep(0)
                counter = cur + 1
            else:
                counter += 1

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    expected = n_threads * n_iter
    return fail() if counter != expected else ok()


def f_never_repro() -> int:
    return ok()


def f_load_conc4() -> int:
    n = int(os.environ.get("CNF0020_CONCURRENCY", "4"))
    hits: list[int] = []
    barrier = threading.Barrier(n)

    def worker() -> None:
        barrier.wait(timeout=2)
        hits.append(time.perf_counter_ns())

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    hits.sort()
    # Collision window 50us: under 4-way start this is intermittent, not 50/50.
    window = 50_000
    collided = any(hits[i + 1] - hits[i] < window for i in range(len(hits) - 1))
    return fail() if collided else ok()


def f_time_jitter() -> int:
    return fail() if (time.time_ns() % 5) == 0 else ok()


def f_always_red() -> int:
    return fail()


HANDLERS = {
    "F-CRLF-ARTEFACT": f_crlf_artefact,
    "F-COIN-P30": f_coin_p30,
    "F-RACE-COUNTER": f_race_counter,
    "F-NEVER-REPRO": f_never_repro,
    "F-LOAD-CONC4": f_load_conc4,
    "F-TIME-JITTER": f_time_jitter,
    "F-ALWAYS-RED": f_always_red,
}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    fid = None
    if "--id" in args:
        fid = args[args.index("--id") + 1]
    elif args:
        fid = args[0]
    if not fid or fid not in HANDLERS:
        print(f"FAILED:CNF-0020 unknown failure id {fid!r}", file=sys.stderr)
        return 2
    if fid == "F-CRLF-ARTEFACT" and not CRLF_FIXTURE.is_file():
        CRLF_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        CRLF_FIXTURE.write_bytes(b"gated-file\r\nsecond-line\r\n")
    return HANDLERS[fid]()


if __name__ == "__main__":
    raise SystemExit(main())
