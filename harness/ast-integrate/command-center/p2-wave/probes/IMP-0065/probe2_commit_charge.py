#!/usr/bin/env python3
"""Probe 2: independent RSS/commit-proxy reading + dead-shared isolation.

Signal (2) of the catalog evidence pair: `ps` RSS (not /proc status) over the
same N-session eager vs shared interval. A process-count drop with no RSS drop
is treated as move-not-merge.

Also the reviewer check: SIGKILL the shared child; the next session call must
raise SharedServerDeadError inside 1.5s and must not hang on stdin.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import mcp_activation as A  # noqa: E402

N = 8
SERVER = "demo"
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0065.json"
HANG_S = 1.5


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0065-probe2 {msg}")
    return 1


def ps_rss_kb(mark: str) -> tuple[int, int]:
    """Parse `ps` ourselves so this probe does not share the library parser."""
    proc = subprocess.run(
        ["ps", "-eo", "pid,rss,args"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    rss_kb = 0
    n = 0
    for line in (proc.stdout or "").splitlines()[1:]:
        if "stub_mcp_server.py" not in line or mark not in line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        try:
            rss_kb += int(parts[1])
        except ValueError:
            continue
        n += 1
    return n, rss_kb


def deadline_call(fn, timeout: float = HANG_S):
    box: dict = {}

    def run() -> None:
        try:
            box["result"] = fn()
        except Exception as exc:  # noqa: BLE001
            box["exc"] = exc

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError(f"hang: still running after {timeout}s")
    if "exc" in box:
        raise box["exc"]
    return box.get("result")


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:IMP-0065" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"receipt state={doc.get('state')}")

    shared_mark = f"p2s{uuid.uuid4().hex[:10]}"
    eager_mark = f"p2e{uuid.uuid4().hex[:10]}"

    with A.make_pool(A.Mode.SHARED_HTTP, shared_mark) as shared:
        for i in range(N):
            shared.open_session(f"s{i}").call(SERVER, {"op": "ping"})
        shared_n, shared_rss = ps_rss_kb(shared_mark)
        procfs_shared = A.rss_swap_bytes_procfs(shared_mark)

    with A.make_pool(A.Mode.EAGER_STDIO, eager_mark) as eager:
        for i in range(N):
            eager.open_session(f"s{i}").call(SERVER, {"op": "ping"})
        eager_n, eager_rss = ps_rss_kb(eager_mark)
        procfs_eager = A.rss_swap_bytes_procfs(eager_mark)

    if shared_n != 1:
        return fail(f"ps shared n={shared_n} want 1")
    if eager_n != N:
        return fail(f"ps eager n={eager_n} want {N}")
    if eager_rss <= 0 or shared_rss <= 0:
        return fail(f"ps RSS zero shared={shared_rss} eager={eager_rss}")
    # Move-not-merge: count dropped but commit/RSS did not.
    if eager_rss < shared_rss * 2:
        return fail(
            f"RSS did not drop with process count "
            f"shared_rss_kb={shared_rss} eager_rss_kb={eager_rss} "
            "(looks like processes moved, not merged)"
        )

    # Failure isolation on a fresh shared pool.
    iso_mark = f"p2k{uuid.uuid4().hex[:10]}"
    hang = False
    elapsed = None
    raised = False
    with A.make_pool(A.Mode.LAZY_SHARED, iso_mark) as pool:
        s0 = pool.open_session("alive")
        s0.call(SERVER, {"op": "ping"})
        pool.kill_shared(SERVER)
        t0 = time.monotonic()
        try:
            deadline_call(lambda: pool.open_session("after").call(SERVER, {"op": "ping"}))
        except TimeoutError:
            hang = True
            elapsed = time.monotonic() - t0
        except A.SharedServerDeadError:
            raised = True
            elapsed = time.monotonic() - t0
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - t0
            return fail(f"unexpected {type(exc).__name__}: {exc}")

    if hang:
        return fail(f"session hung {elapsed:.3f}s on dead shared server")
    if not raised:
        return fail("dead shared server did not raise SharedServerDeadError")
    if elapsed is None or elapsed >= HANG_S:
        return fail(f"dead-server path too slow {elapsed}")

    documented = False
    impl = (PLUGIN / "mcp_activation.py").read_text(encoding="utf-8")
    if "SharedServerDeadError" in impl and "will not hang" in impl:
        documented = True
    if not documented:
        return fail("shared-dead failure mode not documented on the call path")

    out = {
        "probe": "probe2-commit-charge",
        "unit_id": "IMP-0065",
        "n_sessions": N,
        "ps_shared_n": shared_n,
        "ps_eager_n": eager_n,
        "ps_shared_rss_kb": shared_rss,
        "ps_eager_rss_kb": eager_rss,
        "procfs_shared": procfs_shared,
        "procfs_eager": procfs_eager,
        "rss_dropped_with_count": eager_rss >= shared_rss * 2,
        "dead_shared_raised": raised,
        "dead_shared_hang": hang,
        "dead_shared_elapsed_s": round(elapsed, 4),
        "failure_mode_documented": documented,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"ps_rss_kb shared={shared_rss} eager={eager_rss} "
        f"dead_raised={raised} elapsed_s={elapsed:.3f}"
    )
    print("SUCCESS:IMP-0065-probe2 ps-RSS drop + loud shared-dead (no hang)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
