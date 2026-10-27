#!/usr/bin/env python3
"""Free the 4 slow G-1-fix boxes from leftover 281 contention; keep 281 on idle boxes."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=12",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "IdentitiesOnly=yes",
    "-i",
    str(Path.home() / ".ssh" / "id_ed25519"),
]
SLOW = [
    ("par-c", "57.130.46.182"),
    ("rbx-c", "152.228.192.99"),
    ("uk1-a", "54.37.3.247"),
    ("uk1-c", "54.37.7.164"),
]
# leftover dispatcher prompt contains this unique phrase; g1fix prompt does not
KILL = (
    "systemctl stop p2-supervisor; "
    "pkill -f 'on this Linux worktree' || true; "
    "sleep 1; "
    "echo SVC $(systemctl is-active p2-supervisor); "
    "echo LEFTOVER_AGENTS $(pgrep -cf 'on this Linux worktree' || true); "
    "echo G1FIX $(pgrep -cf 'Fix THIS unit only' || true); "
    "echo FIXPY $(pgrep -cf fix_g1_fails.py || true); "
    "tail -n 3 /opt/p2/g1-fix.log 2>/dev/null"
)


def one(name: str, ip: str) -> str:
    p = run(SSH + [f"root@{ip}", KILL], capture_output=True, text=True, timeout=30)
    body = ((p.stdout or "") + (p.stderr or "")).strip().replace("\n", " | ")
    return f"{name:8s} {body[:400]}"


def main() -> None:
    with ThreadPoolExecutor(4) as ex:
        futs = [ex.submit(one, *b) for b in SLOW]
        for f in as_completed(futs):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
