#!/usr/bin/env python3
"""Windows actuator for the process-hygiene supervisor.

This is the ONLY module that mutates OS state (taskkill, wsl --shutdown, and the
cursor-orphan reaper). ``hygiene.py`` decides; this actuates. All OS boundaries
go through three injectable seams (``runner`` / ``prober`` / ``sleeper``) so the
safety logic - identity revalidation before a kill, graceful-stop-then-force, and
reaper-output parsing - is unit-tested without touching a real process, while the
raw subprocess/CIM calls themselves are the untested (``# pragma: no cover``)
edge that only ever runs on Windows.

Kill contract (mirrors the reaper and the estate's hard lessons):
* the tree arrives children-first (deepest process first, root last);
* each PID's identity (creation time + executable) is re-queried immediately
  before the kill - a recycled PID or a changed image aborts that member;
* a graceful ``taskkill /PID`` is tried first, then ``/F`` only if it survives;
* nothing is ever killed by name, and ``/T`` tree discovery is never used.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable

from hygiene import StopResult, _norm


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def _default_runner(args: list[str]) -> RunResult:  # pragma: no cover - real OS
    completed = subprocess.run(args, capture_output=True, text=True, timeout=120)
    return RunResult(
        completed.returncode, completed.stdout or "", completed.stderr or ""
    )


def _default_prober(pid: int) -> dict[str, Any] | None:  # pragma: no cover - real OS
    script = (
        '$p = Get-CimInstance Win32_Process -Filter "ProcessId=%d" '
        "-ErrorAction SilentlyContinue; if ($null -eq $p) { '' } else { "
        "@{ created=([DateTimeOffset]$p.CreationDate).ToUnixTimeSeconds(); "
        "exe=[string]$p.ExecutablePath } | ConvertTo-Json -Compress }" % pid
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    text = (completed.stdout or "").strip()
    if not text:
        return None
    payload = json.loads(text)
    return {"created_unix": int(payload["created"]), "executable": str(payload["exe"])}


class WindowsActuator:
    def __init__(
        self,
        policy: dict[str, Any],
        *,
        run_id: str,
        runner: Callable[[list[str]], RunResult] | None = None,
        prober: Callable[[int], dict[str, Any] | None] | None = None,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
        poll_seconds: float = 1.0,
    ) -> None:
        self.policy = policy
        self.run_id = run_id
        self._run = runner or _default_runner
        self._probe = prober or _default_prober
        self._now = clock or time.monotonic
        self._sleep = sleeper or time.sleep  # pragma: no cover - trivial default
        self._poll = poll_seconds

    # -- process trees ---------------------------------------------------

    def stop_tree(self, tree, *, graceful_seconds: int) -> list[StopResult]:
        return [self._stop_one(member, graceful_seconds) for member in tree]

    def _identity_matches(self, member, identity: dict[str, Any]) -> bool:
        return identity["created_unix"] == member.created_unix and _norm(
            identity["executable"]
        ) == _norm(member.executable)

    def _stop_one(self, member, graceful_seconds: int) -> StopResult:
        identity = self._probe(member.pid)
        if identity is None:
            return StopResult(
                member.pid, member.created_unix, "vanished", "gone before kill"
            )
        if not self._identity_matches(member, identity):
            return StopResult(
                member.pid,
                member.created_unix,
                "identity-changed",
                "creation time or executable changed; refused",
            )
        if graceful_seconds > 0:
            self._run(["taskkill", "/PID", str(member.pid)])
            deadline = self._now() + graceful_seconds
            while self._now() < deadline:
                if self._probe(member.pid) is None:
                    return StopResult(
                        member.pid, member.created_unix, "graceful", "exited on request"
                    )
                self._sleep(self._poll)
        result = self._run(["taskkill", "/PID", str(member.pid), "/F"])
        after = self._probe(member.pid)
        if after is None or not self._identity_matches(member, after):
            return StopResult(
                member.pid,
                member.created_unix,
                "forced",
                f"taskkill rc={result.returncode}",
            )
        return StopResult(
            member.pid,
            member.created_unix,
            "failed",
            f"survived taskkill rc={result.returncode}",
        )

    # -- wsl -------------------------------------------------------------

    def wsl_shutdown(self) -> StopResult:
        result = self._run([self.policy["integration"]["wslExe"], "--shutdown"])
        outcome = "ok" if result.returncode == 0 else "failed"
        return StopResult(0, 0, outcome, f"wsl --shutdown rc={result.returncode}")

    # -- reaper ----------------------------------------------------------

    def run_reaper(self, *, apply: bool) -> dict[str, Any]:
        integration = self.policy["integration"]
        args = [
            integration["powershell"],
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            integration["reaperPath"],
            "-StateFile",
            integration["reaperStateFile"],
            "-EvidenceRoot",
            integration["reaperEvidenceRoot"],
        ]
        if apply:
            args.append("-Apply")
        result = self._run(args)
        parsed: dict[str, Any] = {"exit_code": result.returncode}
        for line in reversed((result.stdout or "").splitlines()):
            stripped = line.strip()
            if stripped.startswith("{"):
                try:
                    parsed.update(json.loads(stripped))
                except json.JSONDecodeError:
                    continue
                break
        parsed.setdefault("status", "error" if result.returncode else "success")
        return parsed
