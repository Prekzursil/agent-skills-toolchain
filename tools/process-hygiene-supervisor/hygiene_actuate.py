#!/usr/bin/env python3
"""Windows actuator for the process-hygiene supervisor.

This is the ONLY module that mutates OS state (process termination,
``wsl --terminate``, and the cursor-orphan reaper). ``hygiene.py`` decides; this
actuates. The OS boundary is two injectable seams - ``opener`` (returns a pinned
process handle) and ``runner`` (spawns a command) - so the safety logic is
unit-tested without touching a real process, while the ctypes/subprocess edges
stay ``# pragma: no cover`` and Windows-only.

Kill contract, and the incident lessons behind each line:

* The tree arrives children-first (deepest process first, root last): Windows
  does not cascade termination, so a parent killed first strands its children.
* ONE handle is opened per member with ``PROCESS_QUERY_LIMITED_INFORMATION |
  PROCESS_TERMINATE | SYNCHRONIZE`` and held from identity validation through
  ``TerminateProcess`` and the exit wait. A PID cannot be recycled while a handle
  to it is open, so the kill can never land on a newcomer that reused the number
  (``taskkill /F`` reopens by PID and cannot give that guarantee).
* Identity = creation time (+/- 1 s, CIM rounds) AND executable path, read from
  THAT handle; a mismatch aborts the member.
* Polite stop is OPT-IN (``integration.politeStopSeconds`` > 0). ``taskkill /PID``
  without ``/F`` posts WM_CLOSE only to windows the process owns; a windowless
  console process (node.exe agent session, python MCP server) is refused
  ("can only be terminated forcefully"), in which case the actuator forces at
  once rather than burning the grace window. Never used against a console lead:
  closing its console would CTRL_CLOSE every process attached to it.
* Nothing is ever killed by name and ``taskkill /T`` is never used.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from hygiene import StopResult, _norm

EXIT_WAIT_SECONDS = 5.0
WINDOWS_EPOCH_DELTA = 11_644_473_600  # seconds between 1601-01-01 and 1970-01-01


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class ProcessHandle(Protocol):
    def identity(self) -> dict[str, Any] | None: ...

    def terminate(self) -> bool: ...

    def set_memory_priority(self, level: int) -> bool: ...

    def wait(self, seconds: float) -> bool: ...

    def close(self) -> None: ...


def filetime_to_unix(filetime: int) -> int:
    return int(filetime // 10_000_000 - WINDOWS_EPOCH_DELTA)


def _default_runner(args: list[str]) -> RunResult:  # pragma: no cover - real OS
    # errors="replace": wsl.exe emits UTF-16LE unless WSL_UTF8=1, and a strict
    # locale decode of that would raise inside the actuator. The env override
    # asks for UTF-8 regardless of how hygiene.py was launched.
    env = dict(os.environ, WSL_UTF8="1")
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=180,
        env=env,
    )
    return RunResult(
        completed.returncode, completed.stdout or "", completed.stderr or ""
    )


def _default_open(pid: int) -> ProcessHandle | None:
    """Open and pin a process by PID (Windows only).

    Returns None when the process no longer exists, raises PermissionError when it
    exists but cannot be opened (elevated / protected), otherwise a handle.
    """
    if os.name != "nt":
        raise OSError("process handles can only be opened on Windows")
    return _Win32Handle.open(pid)  # pragma: no cover - real OS


class _Win32Handle:  # pragma: no cover - real OS, exercised only on Windows
    """A pinned process handle over kernel32 with EXPLICIT prototypes.

    Every function used here is declared with argtypes/restype. Without them
    ctypes assumes C ``int`` for every argument and return value, which silently
    truncates a 64-bit HANDLE on Win64 - a wrong handle value that CloseHandle
    rejects at best and that names some other object at worst. This is exactly
    the class of defect Linux CI cannot reach, so the prototypes are the test.
    """

    PROCESS_TERMINATE = 0x0001
    PROCESS_SET_INFORMATION = 0x0200
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    SYNCHRONIZE = 0x00100000
    ProcessMemoryPriority = 0  # PROCESS_INFORMATION_CLASS
    STILL_ACTIVE = 259
    WAIT_OBJECT_0 = 0
    INFINITE = 0xFFFFFFFF
    ERROR_INVALID_PARAMETER = 87
    ERROR_ACCESS_DENIED = 5
    _kernel32 = None

    @classmethod
    def _k32(cls):
        if cls._kernel32 is None:
            import ctypes
            from ctypes import wintypes

            k = ctypes.WinDLL("kernel32", use_last_error=True)
            k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            k.OpenProcess.restype = wintypes.HANDLE
            k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, wintypes.LPDWORD]
            k.GetExitCodeProcess.restype = wintypes.BOOL
            k.GetProcessTimes.argtypes = [
                wintypes.HANDLE,
                wintypes.LPFILETIME,
                wintypes.LPFILETIME,
                wintypes.LPFILETIME,
                wintypes.LPFILETIME,
            ]
            k.GetProcessTimes.restype = wintypes.BOOL
            k.QueryFullProcessImageNameW.argtypes = [
                wintypes.HANDLE,
                wintypes.DWORD,
                wintypes.LPWSTR,
                wintypes.PDWORD,
            ]
            k.QueryFullProcessImageNameW.restype = wintypes.BOOL
            k.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
            k.TerminateProcess.restype = wintypes.BOOL
            k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            k.WaitForSingleObject.restype = wintypes.DWORD
            k.CloseHandle.argtypes = [wintypes.HANDLE]
            k.CloseHandle.restype = wintypes.BOOL
            k.SetProcessInformation.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                ctypes.c_void_p,
                wintypes.DWORD,
            ]
            k.SetProcessInformation.restype = wintypes.BOOL
            cls._kernel32 = k
        return cls._kernel32

    def __init__(self, handle):
        self._h = handle

    @classmethod
    def open(cls, pid: int):
        import ctypes

        k = cls._k32()
        access = (
            cls.PROCESS_QUERY_LIMITED_INFORMATION
            | cls.PROCESS_TERMINATE
            | cls.PROCESS_SET_INFORMATION
            | cls.SYNCHRONIZE
        )
        handle = k.OpenProcess(access, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error == cls.ERROR_INVALID_PARAMETER:
                return None
            raise PermissionError(f"OpenProcess({pid}) failed: Win32 error {error}")
        return cls(handle)

    def identity(self):
        import ctypes
        from ctypes import wintypes

        k = self._k32()
        code = wintypes.DWORD()
        if not k.GetExitCodeProcess(self._h, ctypes.byref(code)):
            return None
        if code.value != self.STILL_ACTIVE:
            return None
        creation, exit_, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not k.GetProcessTimes(
            self._h,
            ctypes.byref(creation),
            ctypes.byref(exit_),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return None
        filetime = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        executable = ""
        if k.QueryFullProcessImageNameW(self._h, 0, buffer, ctypes.byref(size)):
            executable = buffer.value
        return {"created_unix": filetime_to_unix(filetime), "executable": executable}

    def terminate(self) -> bool:
        return bool(self._k32().TerminateProcess(self._h, 1))

    def set_memory_priority(self, level: int) -> bool:
        import ctypes

        # MEMORY_PRIORITY_INFORMATION is a single ULONG (1 = VERY_LOW .. 5 = NORMAL)
        value = ctypes.c_uint32(int(level))
        return bool(
            self._k32().SetProcessInformation(
                self._h,
                self.ProcessMemoryPriority,
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
        )

    def wait(self, seconds: float) -> bool:
        millis = min(int(seconds * 1000), self.INFINITE - 1)
        return self._k32().WaitForSingleObject(self._h, millis) == self.WAIT_OBJECT_0

    def close(self) -> None:
        self._k32().CloseHandle(self._h)


class WindowsActuator:
    def __init__(
        self,
        policy: dict[str, Any],
        *,
        run_id: str,
        opener: Callable[[int], ProcessHandle | None] | None = None,
        runner: Callable[[list[str]], RunResult] | None = None,
    ) -> None:
        self.policy = policy
        self.run_id = run_id
        self._open = opener or _default_open
        self._run = runner or _default_runner

    # -- process trees ---------------------------------------------------

    def stop_tree(self, tree, *, graceful_seconds: int) -> list[StopResult]:
        return [self._stop_one(member, graceful_seconds) for member in tree]

    @staticmethod
    def _identity_matches(member, identity: dict[str, Any]) -> bool:
        return abs(int(identity["created_unix"]) - member.created_unix) <= 1 and _norm(
            identity["executable"]
        ) == _norm(member.executable)

    def _stop_one(self, member, polite_seconds: int) -> StopResult:
        def result(outcome: str, detail: str) -> StopResult:
            return StopResult(member.pid, member.created_unix, outcome, detail)

        try:
            handle = self._open(member.pid)
        except PermissionError as exc:
            return result("failed", f"cannot open process: {exc}")
        if handle is None:
            return result("vanished", "gone before kill")
        try:
            identity = handle.identity()
            if identity is None:
                return result("vanished", "exited before kill")
            if not self._identity_matches(member, identity):
                return result(
                    "identity-changed", "creation time or executable changed; refused"
                )
            note = ""
            if polite_seconds > 0:
                polite = self._run(["taskkill", "/PID", str(member.pid)])
                if polite.returncode == 0:
                    if handle.wait(polite_seconds):
                        return result("graceful", "exited on WM_CLOSE")
                else:
                    note = f"polite stop refused (taskkill rc={polite.returncode}); "
            if not handle.terminate():
                if handle.wait(0):
                    return result("forced", f"{note}exited as TerminateProcess ran")
                return result("failed", f"{note}TerminateProcess failed")
            if handle.wait(EXIT_WAIT_SECONDS):
                return result("forced", f"{note}terminated on the pinned handle")
            return result(
                "failed",
                f"{note}still alive {EXIT_WAIT_SECONDS:.0f}s after TerminateProcess",
            )
        finally:
            handle.close()

    # -- memory priority (Q7, opt-in) -------------------------------------

    def set_memory_priority(self, member, level: int) -> StopResult:
        """Set a process's memory priority on a pinned, identity-checked handle.

        A priority is a HINT to the memory manager about whose pages to trim first;
        it never frees anything by itself. The same identity guard as the kill
        path applies: a recycled PID is refused, an unopenable one is 'failed'.
        """
        want = "restored" if level >= 5 else "demoted"

        def result(outcome: str, detail: str) -> StopResult:
            return StopResult(member.pid, member.created_unix, outcome, detail)

        try:
            handle = self._open(member.pid)
        except PermissionError as exc:
            return result("failed", f"cannot open process: {exc}")
        if handle is None:
            return result("vanished", "gone before the priority change")
        try:
            identity = handle.identity()
            if identity is None:
                return result("vanished", "exited before the priority change")
            if not self._identity_matches(member, identity):
                return result(
                    "identity-changed", "creation time or executable changed; refused"
                )
            if not handle.set_memory_priority(level):
                return result(
                    "failed", "SetProcessInformation(ProcessMemoryPriority) failed"
                )
            return result(want, f"memory priority set to {level}")
        finally:
            handle.close()

    # -- wsl -------------------------------------------------------------

    def wsl_shutdown(self, *, distros=(), action: str = "terminate") -> StopResult:
        wsl = self.policy["integration"]["wslExe"]
        if action == "shutdown":
            outcome = self._run([wsl, "--shutdown"])
            state = "ok" if outcome.returncode == 0 else "failed"
            return StopResult(0, 0, state, f"wsl --shutdown rc={outcome.returncode}")
        if not distros:
            return StopResult(0, 0, "ok", "nothing to terminate")
        failures = []
        for distro in distros:
            outcome = self._run([wsl, "--terminate", distro])
            if outcome.returncode != 0:
                failures.append(f"{distro} rc={outcome.returncode}")
        if failures:
            return StopResult(
                0, 0, "failed", "wsl --terminate failed: " + ", ".join(failures)
            )
        return StopResult(0, 0, "ok", "wsl --terminate " + ", ".join(distros))

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
        outcome = self._run(args)
        parsed: dict[str, Any] = {"exit_code": outcome.returncode}
        for line in reversed((outcome.stdout or "").splitlines()):
            stripped = line.strip()
            if stripped.startswith("{"):
                try:
                    parsed.update(json.loads(stripped))
                except json.JSONDecodeError:
                    continue
                break
        parsed.setdefault("status", "error" if outcome.returncode else "success")
        return parsed
