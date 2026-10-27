"""Instrumented process/network ports for hermetic simulation (IMP-0199).

A context manager that MONKEYPATCHES the real escape hatches — ``socket``
connections, ``subprocess`` spawns, ``os.system`` — for the duration of a
simulation. Every attempt is counted; spawns raise :class:`SpawnBlocked` and
egress raises :class:`EgressBlocked`, so an escaping rail is both detected and
contained. Two independent signals (these counters and the rail's own ledger)
must agree; disagreement is a failure, not a picked winner.
"""
from __future__ import annotations

import os
import socket
import subprocess
from typing import Any


class SpawnBlocked(RuntimeError):
    """A real process spawn was attempted inside an instrumented simulation."""


class EgressBlocked(RuntimeError):
    """A real network egress was attempted inside an instrumented simulation."""


class InstrumentedPorts:
    """Count and block real spawn/egress attempts while active."""

    def __init__(self) -> None:
        self.real_spawns = 0
        self.egress_attempts = 0
        self.spawn_argvs: list[tuple[str, ...]] = []
        self.egress_targets: list[str] = []
        self._saved: dict[str, Any] = {}

    # -- context management ---------------------------------------------------

    def __enter__(self) -> "InstrumentedPorts":
        ports = self

        def blocked_popen(*args: Any, **kwargs: Any) -> Any:
            ports.real_spawns += 1
            argv = args[0] if args else kwargs.get("args")
            if isinstance(argv, (list, tuple)):
                ports.spawn_argvs.append(tuple(str(a) for a in argv))
            elif argv is not None:
                ports.spawn_argvs.append((str(argv),))
            raise SpawnBlocked(f"real spawn blocked: {argv!r}")

        def blocked_system(command: Any) -> int:
            ports.real_spawns += 1
            ports.spawn_argvs.append((str(command),))
            raise SpawnBlocked(f"os.system blocked: {command!r}")

        def blocked_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
            ports.egress_attempts += 1
            ports.egress_targets.append(str(address))
            raise EgressBlocked(f"egress blocked: {address!r}")

        real_connect = socket.socket.connect

        def blocked_connect(sock: Any, address: Any) -> Any:  # noqa: ANN001
            ports.egress_attempts += 1
            ports.egress_targets.append(str(address))
            raise EgressBlocked(f"egress blocked: {address!r}")

        self._saved = {
            "Popen": subprocess.Popen,
            "system": os.system,
            "create_connection": socket.create_connection,
            "connect": real_connect,
        }
        subprocess.Popen = blocked_popen  # type: ignore[misc,assignment]
        os.system = blocked_system  # type: ignore[assignment]
        socket.create_connection = blocked_create_connection  # type: ignore[assignment]
        socket.socket.connect = blocked_connect  # type: ignore[method-assign,assignment]
        return self

    def __exit__(self, *exc: Any) -> None:
        subprocess.Popen = self._saved["Popen"]  # type: ignore[misc]
        os.system = self._saved["system"]  # type: ignore[assignment]
        socket.create_connection = self._saved["create_connection"]  # type: ignore[assignment]
        socket.socket.connect = self._saved["connect"]  # type: ignore[method-assign]
        self._saved = {}

    # -- reporting -------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return {
            "real_spawns": self.real_spawns,
            "egress_attempts": self.egress_attempts,
            "spawn_argvs": [list(a) for a in self.spawn_argvs],
            "egress_targets": list(self.egress_targets),
        }


__all__ = ["EgressBlocked", "InstrumentedPorts", "SpawnBlocked"]
