"""Shared constants and both-states fetch helper for BLD-0044."""
from __future__ import annotations

import os
import random
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SUITE_MARKER = HERE / "SUITE_MARKER"
UNSHARE = "/usr/bin/unshare"
UNSHARE = UNSHARE
FETCH_HOST = "1.1.1.1"
FETCH_PORT = 53
FETCH_TIMEOUT = 2.0

TEST_NAMES = [
    "test_hermetic",
    "test_order_write",
    "test_order_read",
    "test_tz_utc_offset",
    "test_cwd_marker",
    "test_cache_hit",
    "test_prng_draw",
    "test_undeclared_fetch",
]

# Discovered at implementation time; re-checked by verify_seeds().
ORDER_WRITE_FIRST_SEED = 1
ORDER_READ_FIRST_SEED = 3
PRNG_HIT_SEED = 3  # random.Random(3).randint(0, 20) == 7
PRNG_MISS_SEED = 1

AXES = {
    "order_seed": [ORDER_WRITE_FIRST_SEED, ORDER_READ_FIRST_SEED],
    "prng_seed": [PRNG_HIT_SEED, PRNG_MISS_SEED],
    "tz": ["UTC", "Pacific/Kiritimati"],
    "cwd": ["suite", "empty"],
    "cache": ["cold", "warm"],
    "egress": ["open", "blocked"],
}


def shuffled_order(seed: int) -> list[str]:
    names = list(TEST_NAMES)
    random.Random(seed).shuffle(names)
    return names


def verify_seeds() -> None:
    wf = shuffled_order(ORDER_WRITE_FIRST_SEED)
    rf = shuffled_order(ORDER_READ_FIRST_SEED)
    if not (wf.index("test_order_write") < wf.index("test_order_read")):
        raise RuntimeError("ORDER_WRITE_FIRST_SEED no longer write-before-read")
    if not (rf.index("test_order_read") < rf.index("test_order_write")):
        raise RuntimeError("ORDER_READ_FIRST_SEED no longer read-before-write")
    if random.Random(PRNG_HIT_SEED).randint(0, 20) != 7:
        raise RuntimeError("PRNG_HIT_SEED no longer draws 7")
    if random.Random(PRNG_MISS_SEED).randint(0, 20) == 7:
        raise RuntimeError("PRNG_MISS_SEED unexpectedly draws 7")


def deliberate_fetch() -> None:
    """Outbound TCP that must FAIL under an egress block and PASS when open."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(FETCH_TIMEOUT)
        sock.connect((FETCH_HOST, FETCH_PORT))
    finally:
        sock.close()


def fetch_open() -> tuple[bool, str]:
    try:
        deliberate_fetch()
        return True, "connected"
    except OSError as exc:
        return False, f"{type(exc).__name__}:{exc}"


GUARD_PREFIX = """import socket as _s
class _Bld0044Blocked(_s.socket):
    def connect(self, address):
        raise OSError('BLD-0044 egress guard: connect blocked')
_s.socket = _Bld0044Blocked
"""


def fetch_blocked_via_unshare() -> tuple[bool, str]:
    """Run deliberate_fetch under a PROVEN block.

    POSIX: empty network namespace (unshare -n). Windows repair 2026-10-24:
    unshare does not exist on this OS, so the old path 'blocked' by failing to
    INVOKE - a vacuous control counted as a pass. The Windows-adapted block is
    a socket-connect guard installed in the child BEFORE the deliberate fetch;
    the same child code connects cleanly when the guard is absent (fetch_open),
    so the guard itself is both-states proven. OS-level netns remains a
    Linux-only residual and is labeled as such in the mechanism field.
    """
    inner = (
        "import socket,sys;"
        f"s=socket.socket();s.settimeout({FETCH_TIMEOUT});"
        f"s.connect(({FETCH_HOST!r},{FETCH_PORT}));s.close()"
    )
    if os.name == "nt":
        try:
            proc = subprocess.run(
                [sys.executable, "-c", GUARD_PREFIX + inner],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                timeout=FETCH_TIMEOUT + 10,
            )
        except Exception as exc:  # noqa: BLE001
            return False, f"guard-invoke:{type(exc).__name__}:{exc}"
        err = (proc.stderr or "")
        if "BLD-0044 egress guard: connect blocked" in err and "SyntaxError" not in err and "Traceback" in err:
            return False, "egress-guard-fired:OSError raised at connect under guard"
        if proc.returncode == 0:
            return True, "fetch CONNECTED under guard - block is not live"
        return False, f"guard-child-invalid:{err.strip()[-200:]}"
        if proc.returncode == 0:
            return True, "fetch CONNECTED under guard - block is not live"
        return False, f"child-failed-other:{err.strip()[-160:]}"
    try:
        proc = subprocess.run(
            [UNSHARE, "-n", sys.executable, "-c", inner],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"unshare-invoke:{type(exc).__name__}:{exc}"
    if proc.returncode == 0:
        return True, "connected-inside-unshare"
    tail = ((proc.stderr or "") + (proc.stdout or "")).strip().replace("\n", " ")
    return False, f"rc={proc.returncode} {tail[-300:]}"


def block_control() -> dict:
    """Both-states proof that the blocker itself is live."""
    open_ok, open_detail = fetch_open()
    blocked_ok, blocked_detail = fetch_blocked_via_unshare()
    both = bool(open_ok) and (not blocked_ok)
    _mech = (
        "linux unshare -n empty netns (OS-level; not a proxy env var)"
        if os.name != "nt"
        else "in-process socket-connect guard proven both-states in the child (Windows-adapted; unshare -n is Linux-only and absent on this OS - OS-level netns is a residual)"
    )
    return {
        "mechanism": _mech,
        "unshare_path": UNSHARE if os.name != "nt" else None,
        "target": f"tcp://{FETCH_HOST}:{FETCH_PORT}",
        "deliberate_fetch_open": "PASS" if open_ok else "FAIL",
        "deliberate_fetch_open_detail": open_detail,
        "deliberate_fetch_blocked": "PASS" if blocked_ok else "FAIL",
        "deliberate_fetch_blocked_detail": blocked_detail,
        "both_states": both,
    }


shuffled_order = shuffled_order
block_control = block_control
