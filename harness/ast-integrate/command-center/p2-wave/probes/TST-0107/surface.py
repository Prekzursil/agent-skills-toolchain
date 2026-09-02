"""Status/hook invocation runner: 300 ms debounce, cancel slow renders, idle gate."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from path_shim import SpawnShim
from scenario import DEBOUNCE_MS, HERE, PAYLOAD, TIMEOUT_MS


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class RealClock:
    def now(self) -> float:
        return time.monotonic()


@dataclass
class InvokeResult:
    status: str
    returncode: int | None
    stdout: str
    nested_spawns: int
    elapsed_ms: float
    cancelled: bool


class StatusSurface:
    """One mediating entry point for statusline + gated probes."""

    def __init__(
        self,
        shim: SpawnShim,
        debounce_ms: int = DEBOUNCE_MS,
        timeout_ms: int = TIMEOUT_MS,
        clock: Any | None = None,
    ) -> None:
        self.shim = shim
        self.debounce_ms = debounce_ms
        self.timeout_ms = timeout_ms
        self.clock = clock or RealClock()
        self._last_invoke: float | None = None

    def _argv(self, script: Path) -> list[str]:
        return [sys.executable, "-B", str(script)]

    def invoke(
        self,
        script: Path,
        payload: dict | None = None,
        *,
        force: bool = False,
    ) -> InvokeResult:
        now = self.clock.now()
        if (
            not force
            and self._last_invoke is not None
            and (now - self._last_invoke) * 1000 < self.debounce_ms
        ):
            return InvokeResult(
                status="debounced",
                returncode=None,
                stdout="",
                nested_spawns=0,
                elapsed_ms=0.0,
                cancelled=False,
            )
        before = self.shim.nested_helper_count()
        body = json.dumps(payload if payload is not None else PAYLOAD)
        t0 = time.perf_counter()
        try:
            proc = subprocess.run(
                self._argv(script),
                input=body,
                capture_output=True,
                text=True,
                env=self.shim.env(),
                timeout=self.timeout_ms / 1000.0,
                cwd=str(HERE),
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self._last_invoke = self.clock.now()
            return InvokeResult(
                status="ok" if proc.returncode == 0 else "nonzero",
                returncode=proc.returncode,
                stdout=(proc.stdout or "").strip(),
                nested_spawns=self.shim.nested_helper_count() - before,
                elapsed_ms=elapsed_ms,
                cancelled=False,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self._last_invoke = self.clock.now()
            stdout = ""
            if exc.stdout:
                stdout = (
                    exc.stdout.decode("utf-8", errors="replace")
                    if isinstance(exc.stdout, bytes)
                    else str(exc.stdout)
                )
            return InvokeResult(
                status="cancelled",
                returncode=None,
                stdout=stdout.strip(),
                nested_spawns=self.shim.nested_helper_count() - before,
                elapsed_ms=elapsed_ms,
                cancelled=True,
            )

    def session_tick(
        self,
        *,
        idle: bool,
        statusline: Path,
        gated_probe: Path,
        skip_gated_when_idle: bool = True,
    ) -> dict[str, Any]:
        before = self.shim.nested_helper_count()
        gated_run = False
        render = None
        if idle and skip_gated_when_idle:
            nested = self.shim.nested_helper_count() - before
            return {
                "idle": True,
                "gated_probes_run": False,
                "render_status": "skipped-idle",
                "nested_spawns": nested,
            }
        render = self.invoke(statusline, force=True)
        if not idle or not skip_gated_when_idle:
            self.invoke(gated_probe, payload={}, force=True)
            gated_run = True
        return {
            "idle": idle,
            "gated_probes_run": gated_run,
            "render_status": render.status if render else "skipped-idle",
            "nested_spawns": self.shim.nested_helper_count() - before,
        }


INPROC = HERE / "fixtures" / "statusline_inproc.py"
OVERBUDGET = HERE / "fixtures" / "statusline_overbudget.py"
SLOW = HERE / "fixtures" / "statusline_slow.py"
GATED = HERE / "fixtures" / "gated_probe.py"
