"""Run install+tests with egress allowed or blocked; also OS-level netns control."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

from contract import EGRESS_HOST, EGRESS_PORT
from suite import CACHED_PAYLOAD, TESTS, reverify_cache_path, touch_egress
from wrap import install as install_wrap


def _run_steps(block: bool, cache_file: Path) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    with install_wrap(block=block) as guard:
        start = 0
        for name, fn in TESTS:
            rec: dict[str, Any] = {"id": name, "ok": False, "error": None}
            try:
                rec["result"] = fn(cache_file)
                rec["ok"] = True
            except Exception as exc:  # noqa: BLE001 — measurement, record every failure
                rec["error"] = f"{type(exc).__name__}: {exc}"
                rec["traceback_tail"] = traceback.format_exc()[-400:]
            rec["attempted_destinations"] = [
                {"host": a["host"], "port": a["port"], "via": a["via"]}
                for a in guard.attempts[start:]
            ]
            start = len(guard.attempts)
            steps.append(rec)
        all_attempts = [
            {"host": a["host"], "port": a["port"], "via": a["via"]} for a in guard.attempts
        ]
    return {
        "mode": "blocked" if block else "unblocked",
        "completed": True,
        "steps": steps,
        "attempted_destinations": all_attempts,
    }


def block_control_fetch() -> dict[str, Any]:
    with install_wrap(block=True) as guard:
        ok = False
        err = None
        try:
            touch_egress()
            ok = True
        except OSError as exc:
            err = f"{type(exc).__name__}: {exc}"
        dests = [{"host": a["host"], "port": a["port"], "via": a["via"]} for a in guard.attempts]
    return {
        "fetch_succeeded": ok,
        "failed_as_required": (not ok) and len(dests) >= 1,
        "error": err,
        "attempted_destinations": dests,
    }


def os_netns_control() -> dict[str, Any]:
    snippet = (
        "import socket; socket.create_connection(("
        f"'{EGRESS_HOST}', {EGRESS_PORT}), timeout=3)"
    )
    cmd = ["unshare", "-n", sys.executable, "-c", snippet]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    return {
        "command": " ".join(cmd[:4]) + " <create_connection>",
        "exit_code": p.returncode,
        "failed_as_required": p.returncode != 0,
        "stderr_tail": (p.stderr or "")[-300:],
    }


def measure() -> dict[str, Any]:
    """Four measured states: warm/cold × blocked/unblocked, plus block proofs."""
    with tempfile.TemporaryDirectory(prefix="cnf0106-") as tmp:
        tmp_path = Path(tmp)
        warm = tmp_path / "warm" / "payload.bin"
        warm.parent.mkdir(parents=True)
        warm.write_bytes(CACHED_PAYLOAD)
        reverify_cache_path(warm).write_bytes(CACHED_PAYLOAD)

        blocked_warm = _run_steps(block=True, cache_file=warm)

        # Recreate warm caches (lying test does not consume them).
        warm.write_bytes(CACHED_PAYLOAD)
        reverify_cache_path(warm).write_bytes(CACHED_PAYLOAD)
        unblocked_warm = _run_steps(block=False, cache_file=warm)

        cold_b = tmp_path / "cold-blocked" / "payload.bin"
        cold_b.parent.mkdir(parents=True)
        blocked_cold = _run_steps(block=True, cache_file=cold_b)

        cold_u = tmp_path / "cold-unblocked" / "payload.bin"
        cold_u.parent.mkdir(parents=True)
        unblocked_cold = _run_steps(block=False, cache_file=cold_u)

    control = block_control_fetch()
    netns = os_netns_control()
    return {
        "block_control": control,
        "os_netns_control": netns,
        "blocked_warm": blocked_warm,
        "unblocked_warm": unblocked_warm,
        "blocked_cold": blocked_cold,
        "unblocked_cold": unblocked_cold,
    }


def step(run: dict[str, Any], name: str) -> dict[str, Any]:
    for item in run["steps"]:
        if item["id"] == name:
            return item
    raise KeyError(name)
