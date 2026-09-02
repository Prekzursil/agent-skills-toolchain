"""Run locked / unlocked / detector-control / posix-native rollback experiments."""
from __future__ import annotations

import os
import select
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

from inventory import all_version, walk  # noqa: E402
from rollback import rollback  # noqa: E402
from scenario import LOCKED_RELS, UNLOCKED_REL, build_prefix, known_hashes  # noqa: E402

CLIENT = HERE / "client.py"


class HeldClient:
    def __init__(self, paths: list[Path]):
        self.paths = paths
        self.proc: subprocess.Popen | None = None
        self.pid: int | None = None

    def _stop(self) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=2)

    def __enter__(self) -> "HeldClient":
        cmd = [sys.executable, "-u", "-B", str(CLIENT), *[str(p) for p in self.paths]]
        self.proc = subprocess.Popen(
            cmd,
            cwd=str(HERE),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.time() + 5.0
        buf = b""
        fd = self.proc.stdout.fileno() if self.proc.stdout else None
        while time.time() < deadline:
            if self.proc.poll() is not None and b"READY" not in buf:
                err = (self.proc.stderr.read() if self.proc.stderr else b"") or b""
                self._stop()
                raise RuntimeError(
                    f"client exited early rc={self.proc.returncode} {err[-500:]!r}"
                )
            remaining = max(0.01, deadline - time.time())
            ready, _, _ = select.select([self.proc.stdout], [], [], remaining)
            if ready and fd is not None:
                chunk = os.read(fd, 4096)
                if chunk:
                    buf += chunk
            text = buf.decode("utf-8", errors="replace")
            for line in text.splitlines():
                if line.startswith("LOCKER_PID="):
                    self.pid = int(line.split("=", 1)[1].strip())
            if "READY" in text:
                return self
        self._stop()
        raise TimeoutError(f"client not READY: {buf!r}")

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self._stop()


def _strip_roots(inv: dict[str, Any]) -> dict[str, Any]:
    files = []
    for row in inv.get("files") or []:
        files.append(
            {
                "path": row["path"],
                "present": row["present"],
                "sha256": row["sha256"],
                "bytes": row["bytes"],
                "version": row["version"],
            }
        )
    return {"files": files}


def _run(mode: str, hold: bool) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cnf0046-") as tmp:
        paths = build_prefix(Path(tmp))
        prefix = paths["prefix"]
        snapshot = paths["snapshot"]
        snap_inv = _strip_roots(walk(snapshot))
        pre_inv = _strip_roots(walk(prefix))
        locker_pid = None
        if hold:
            held = [prefix / rel for rel in LOCKED_RELS]
            with HeldClient(held) as client:
                locker_pid = client.pid
                result = rollback(prefix, snapshot, mode=mode)
        else:
            result = rollback(prefix, snapshot, mode=mode)
        result["locker_pid_started"] = locker_pid
        result["snapshot"] = snap_inv
        result["pre_installed"] = pre_inv
        result["post"] = _strip_roots(result["post"])
        result["pre"] = _strip_roots(result["pre"])
        result["all_v1"] = all_version({"files": result["post"]["files"]}, "v1")
        result["all_v2"] = all_version({"files": result["post"]["files"]}, "v2")
        if hold and result.get("handle_list"):
            pids = {h.get("pid") for h in result["handle_list"]}
            result["locker_pid_observed"] = locker_pid in pids
            result["error_names_pid"] = (
                locker_pid is not None and str(locker_pid) in (result.get("error_text") or "")
            )
        else:
            result["locker_pid_observed"] = False
            result["error_names_pid"] = False
        result["unlocked_rel"] = UNLOCKED_REL
        result["locked_rels"] = list(LOCKED_RELS)
        return result


def run_suite() -> dict[str, Any]:
    locked_aware = _run("aware", hold=True)
    unlocked = _run("aware", hold=False)
    naive = _run("naive-skip", hold=True)
    posix = _run("posix-replace", hold=True)
    hashes = known_hashes()
    return {
        "known_hashes": hashes,
        "locked_aware": locked_aware,
        "unlocked": unlocked,
        "naive_skip": naive,
        "posix_replace": posix,
        "pass": (
            locked_aware["exit_code"] == 2
            and locked_aware["all_v2"]
            and not locked_aware["mixed_version"]
            and not locked_aware["corrupted"]
            and locked_aware["names_locking_process"]
            and locked_aware["error_names_pid"]
            and not locked_aware["wrote"]
            and unlocked["exit_code"] == 0
            and unlocked["all_v1"]
            and not unlocked["mixed_version"]
            and not unlocked["corrupted"]
            and naive["mixed_version"]
            and not naive["corrupted"]
            and naive["exit_code"] == 0
        ),
    }


if __name__ == "__main__":
    import json

    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    suite = run_suite()
    print(json.dumps({"pass": suite["pass"], "locked_exit": suite["locked_aware"]["exit_code"],
                      "unlocked_exit": suite["unlocked"]["exit_code"],
                      "naive_mixed": suite["naive_skip"]["mixed_version"]}, sort_keys=True))
    raise SystemExit(0 if suite["pass"] else 1)
