#!/usr/bin/env python3
"""Probe 1: OS process-table count for N sessions, shared vs eager.

Signal (1) of the catalog evidence pair. Counts stub PIDs from /proc cmdline
(not from ActivationPool's internal maps). Same-run negative control: eager
mode must reproduce N processes or the counter is inert.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import mcp_activation as A  # noqa: E402

N = 8
SERVER = "demo"
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0065.json"


def _proc_count(mark: str) -> list[int]:
    """Independent /proc walk (duplicated here so probe1 is not a wrapper)."""
    found: list[int] = []
    proc = Path("/proc")
    needle = mark.encode("utf-8")
    stub = b"stub_mcp_server.py"
    for entry in proc.iterdir():
        name = entry.name
        if not name.isdigit():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except (OSError, PermissionError):
            continue
        if stub in raw and needle in raw:
            found.append(int(name))
    return sorted(found)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0065-probe1 {msg}")
    return 1


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:IMP-0065" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"receipt state={doc.get('state')}")

    shared_mark = f"p1s{uuid.uuid4().hex[:10]}"
    eager_mark = f"p1e{uuid.uuid4().hex[:10]}"

    with A.make_pool(A.Mode.LAZY_SHARED, shared_mark) as shared:
        sessions = [shared.open_session(f"s{i}") for i in range(N)]
        before = _proc_count(shared_mark)
        if before:
            return fail(f"lazy open_session already spawned {before}")
        for s in sessions:
            reply = s.call(SERVER, {"op": "ping", "session": s.session_id})
            if reply.get("ok") is not True:
                return fail(f"shared ping failed {reply}")
        shared_pids = _proc_count(shared_mark)
        lib_count = A.process_table_count(shared_mark)
        if lib_count != len(shared_pids):
            return fail(f"library census {lib_count} != probe /proc {len(shared_pids)}")

    with A.make_pool(A.Mode.EAGER_STDIO, eager_mark) as eager:
        for i in range(N):
            eager.open_session(f"s{i}").call(SERVER, {"op": "ping"})
        eager_pids = _proc_count(eager_mark)

    shared_n = len(shared_pids)
    eager_n = len(eager_pids)
    out = {
        "probe": "probe1-process-table",
        "unit_id": "IMP-0065",
        "n_sessions": N,
        "shared_pids": shared_pids,
        "shared_n": shared_n,
        "eager_pids": eager_pids,
        "eager_n": eager_n,
        "negative_control_eager_reproduced_n": eager_n == N,
        "shared_is_one": shared_n == 1,
        "counter_discriminates": eager_n > shared_n,
        "pass": shared_n == 1 and eager_n == N,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"shared_n={shared_n} eager_n={eager_n} n_sessions={N} "
        f"negative_control={eager_n == N}"
    )
    if shared_n != 1:
        return fail(f"shared mode spawned {shared_n} want 1")
    if eager_n != N:
        return fail(f"eager negative control spawned {eager_n} want {N}")
    print("SUCCESS:IMP-0065-probe1 process-table N-sessions→1 shared, eager→N")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
