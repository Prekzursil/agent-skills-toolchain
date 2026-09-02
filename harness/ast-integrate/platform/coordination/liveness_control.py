"""Standalone BOTH-STATES control for the two liveness signals.

Runnable outside pytest so the measurement can be reproduced from a shell and pasted as evidence::

    python platform/coordination/liveness_control.py

It exercises both signals against both states and prints one JSON object. Exit 0 only when EVERY
signal discriminates - a probe that reports the same thing in the known-good and the known-broken
state measures nothing (``rules/common/single-signal-verification.md`` rule 3b).

  signal B (OS lock)     holder running -> HELD-BY-OTHER   holder exited -> FREE
  signal A (heartbeat)   fresh          -> LIVE            stale         -> DEAD
  combined classifier    fresh+held     -> LIVE            stale+free    -> DEAD
                         fresh+free     -> UNVERIFIED      stale+held    -> UNVERIFIED

The two UNVERIFIED rows are the point of the design, so they are asserted too: a classifier that
collapsed a disagreement into DEAD would reap live sessions.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from coordination.oslock import LockOutcome, probe_lock  # noqa: E402
from coordination.session import (  # noqa: E402
    Liveness,
    classify,
    lock_path_for,
    register_session,
)
from coordination.store import Store  # noqa: E402

CHILD = HERE / "lock_probe_child.py"


def _wait_for(path: Path, timeout: float = 30.0) -> str | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            return path.read_text(encoding="utf-8")
        time.sleep(0.05)
    return None


def main() -> int:
    out: dict[str, object] = {
        "control": "phase9-liveness-both-states",
        "platform": sys.platform,
    }
    with tempfile.TemporaryDirectory(prefix="p9live") as td:
        root = Path(td)
        store = Store(root=root / "coord").initialise()
        record, _lock = register_session(
            store,
            vendor="anthropic",
            adapter_id="claude-code",
            tool="claude-code",
            session_id="ctl-session",
            hold_lock=False,
        )
        lock_file = lock_path_for(store, record.session_id)
        ready = root / "ready.txt"

        # ---- STATE ALIVE: a real separate process holds the lock -------------------------
        proc = subprocess.Popen(
            [sys.executable, str(CHILD), str(lock_file), str(ready), "25"]
        )  # noqa: S603
        try:
            out["child_ready"] = _wait_for(ready)
            alive_probe = probe_lock(lock_file)
            out["B_state_alive"] = alive_probe.to_dict()
            out["combined_fresh_held"] = classify(
                store, record, now=record.heartbeat_at + 1.0
            ).liveness.value
            out["combined_stale_held"] = classify(
                store, record, now=record.heartbeat_at + 10_000.0
            ).liveness.value
        finally:
            proc.terminate()
            proc.wait(timeout=30)

        # ---- STATE DEAD: the OS released the lock when the holder exited -----------------
        dead_probe = probe_lock(lock_file)
        out["B_state_dead"] = dead_probe.to_dict()
        out["combined_fresh_free"] = classify(
            store, record, now=record.heartbeat_at + 1.0
        ).liveness.value
        out["combined_stale_free"] = classify(
            store, record, now=record.heartbeat_at + 10_000.0
        ).liveness.value

        # ---- signal B with no file at all: NOT-COMPUTABLE, never FREE --------------------
        lock_file.unlink()
        out["B_state_absent"] = probe_lock(lock_file).to_dict()

    checks = {
        "B_discriminates": (
            out["B_state_alive"]["outcome"] == LockOutcome.HELD_BY_OTHER.value  # type: ignore[index]
            and out["B_state_dead"]["outcome"] == LockOutcome.FREE.value  # type: ignore[index]
        ),
        "B_absent_is_not_computable": (
            out["B_state_absent"]["outcome"] == LockOutcome.NOT_COMPUTABLE.value  # type: ignore[index]
        ),
        "combined_live": out["combined_fresh_held"] == Liveness.LIVE.value,
        "combined_dead": out["combined_stale_free"] == Liveness.DEAD.value,
        "combined_disagreement_is_unverified": (
            out["combined_stale_held"] == Liveness.UNVERIFIED.value
            and out["combined_fresh_free"] == Liveness.UNVERIFIED.value
        ),
    }
    out["checks"] = checks
    out["all_discriminate"] = all(checks.values())
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if out["all_discriminate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
