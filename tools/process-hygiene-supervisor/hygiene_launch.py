#!/usr/bin/env python3
"""hygiene_launch - admission gate + job-object launch shim for agent CLIs.

    python hygiene_launch.py [--runtime NAME] [--job-memory-limit BYTES]
                             [--notify-limit BYTES] [--force] [--dry-run]
                             -- <command> [args...]

Two of the decision queue's prevention items in one small tool:

Q10 ADMISSION. Before launching, read the supervisor's heartbeat (tier, failure
    modes, commit headroom, minutes to the commit limit). A `critical` box, or a
    commit limit less than 30 minutes away at the current slope, REFUSES the new
    session (exit 75, EX_TEMPFAIL) and says what to read; `elevated` admits with a
    warning; `--force` overrides and the override is recorded. The gate FAILS
    OPEN when the heartbeat is missing, stale or unreadable - a gate that blocks
    work because the watchdog died is worse than no gate.

Q1  JOB OBJECT. On Windows the launcher creates a job with KILL_ON_JOB_CLOSE
    (plus an optional JOB_MEMORY hard cap, which fails further commit inside the
    job rather than killing anything), assigns ITSELF to the job, and then spawns
    the command. Every descendant joins the job automatically, so when the
    launcher exits - or is killed - the whole tree goes with it: the orphan class
    the supervisor otherwise mops up cannot form. The handle is non-inheritable
    on purpose (an inherited handle would keep the job alive from inside).
    `--notify-limit` is a soft threshold: the launcher polls PeakJobMemoryUsed and
    warns once when the tree crosses it. Either way it prints a per-session bill
    (peak job memory, duration, exit code) and appends it to sessions.jsonl - the
    "memory ledger per session" that survives child churn.

Off Windows the job step is skipped (posix has no equivalent this cheap) and the
gate + bill still work, which is also what makes the whole flow testable here.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import pathlib
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable

EXIT_REFUSED = 75  # EX_TEMPFAIL: try again later
EXIT_USAGE = 2
EXIT_NOT_FOUND = 127
HEARTBEAT_STALE_SECONDS = 15 * 60
EXHAUSTION_REFUSE_MINUTES = 30

# winnt.h - verified against Microsoft Learn 2026-09-02
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_ulonglong)
        for name in (
            "ReadOperationCount",
            "WriteOperationCount",
            "OtherOperationCount",
            "ReadTransferCount",
            "WriteTransferCount",
            "OtherTransferCount",
        )
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


# ----------------------------------------------------------------- admission


@dataclass
class Verdict:
    admit: bool
    reason: str
    hint: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "admit": self.admit,
            "reason": self.reason,
            "hint": self.hint,
            "warnings": self.warnings,
        }


def read_heartbeat(path) -> dict[str, Any] | None:
    try:
        payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def decide(
    heartbeat: dict[str, Any] | None, *, now: int, force: bool = False
) -> Verdict:
    hint = "python hygiene.py explain --snapshot <fresh snapshot> shows what is holding memory; the ledger's resume_hint rows say how to get stale sessions back"
    if not heartbeat or "tier" not in heartbeat or "ts" not in heartbeat:
        return Verdict(
            True,
            "no usable heartbeat",
            warnings=[
                "supervisor heartbeat missing or malformed; admitting without a memory verdict (fail-open)"
            ],
        )
    age = now - int(heartbeat.get("ts", 0))
    if age > HEARTBEAT_STALE_SECONDS:
        return Verdict(
            True,
            "stale heartbeat",
            warnings=[
                f"supervisor heartbeat is {age // 60} min old; admitting without a memory verdict (fail-open) - run hygiene_doctor.py"
            ],
        )
    tier = str(heartbeat.get("tier"))
    modes = heartbeat.get("pressure_modes") or []
    eta = heartbeat.get("minutes_to_commit_limit")
    refusal = None
    if eta is not None and float(eta) < EXHAUSTION_REFUSE_MINUTES:
        refusal = f"commit limit is {float(eta):.0f} min away at the current slope"
    elif tier == "critical":
        refusal = f"box is critical ({'+'.join(modes) or 'pressure'})"
    if refusal:
        if not force:
            return Verdict(False, refusal, hint)
        return Verdict(
            True, refusal, hint, warnings=[f"forced past a refusal: {refusal}"]
        )
    if tier == "elevated":
        return Verdict(
            True,
            f"tier {tier}",
            warnings=[
                f"box is elevated ({'+'.join(modes) or 'pressure'}); this session adds to it"
            ],
        )
    return Verdict(True, f"tier {tier}")


# ----------------------------------------------------------------- job seam


class _Win32Job:  # pragma: no cover - real OS, exercised only on Windows
    """CreateJobObject + KILL_ON_JOB_CLOSE (+ optional JOB_MEMORY), with explicit
    prototypes so a 64-bit HANDLE is never marshalled through a C int."""

    def __init__(self, limit_bytes: int | None):
        from ctypes import wintypes

        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        k.CreateJobObjectW.restype = wintypes.HANDLE
        k.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        k.SetInformationJobObject.restype = wintypes.BOOL
        k.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.LPDWORD,
        ]
        k.QueryInformationJobObject.restype = wintypes.BOOL
        k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        k.AssignProcessToJobObject.restype = wintypes.BOOL
        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        self._k = k
        # NULL security attributes -> the handle is NOT inheritable, which is what
        # lets closing our handle be the last handle.
        self._h = k.CreateJobObjectW(None, None)
        if not self._h:
            raise OSError(f"CreateJobObject failed: {ctypes.get_last_error()}")
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if limit_bytes:
            info.BasicLimitInformation.LimitFlags |= JOB_OBJECT_LIMIT_JOB_MEMORY
            info.JobMemoryLimit = int(limit_bytes)
        if not k.SetInformationJobObject(
            self._h,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            raise OSError(f"SetInformationJobObject failed: {ctypes.get_last_error()}")

    def assign_current(self) -> bool:
        return bool(
            self._k.AssignProcessToJobObject(self._h, self._k.GetCurrentProcess())
        )

    def peak_bytes(self) -> int:
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        if not self._k.QueryInformationJobObject(
            self._h,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
            None,
        ):
            return 0
        return int(info.PeakJobMemoryUsed)

    def close(self) -> None:
        self._k.CloseHandle(self._h)


def _win32_job(limit_bytes: int | None):
    if os.name != "nt":
        raise OSError(
            "job objects exist only on Windows; the gate and bill still work elsewhere"
        )
    return _Win32Job(limit_bytes)  # pragma: no cover - real OS


# ---------------------------------------------------------------------- run


def _basename(command: str) -> str:
    return pathlib.PurePath(command).name.lower().removesuffix(".exe")


def _stderr(message: str) -> None:
    print(f"[hygiene-launch] {message}", file=sys.stderr)


def _append_bill(path, row: dict[str, Any]) -> None:
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def main(
    argv: list[str] | None = None,
    *,
    now: Callable[[], int] | None = None,
    job_factory=None,
) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    now = now or (lambda: int(time.time()))
    job_factory = job_factory or _win32_job
    if "--" in argv:
        split = argv.index("--")
        own, command = argv[:split], argv[split + 1 :]
    else:
        own, command = argv, []
    parser = argparse.ArgumentParser(prog="hygiene_launch.py", add_help=True)
    default_root = pathlib.Path.home() / ".agent-guard" / "process-hygiene"
    parser.add_argument(
        "--runtime",
        default=None,
        help="runtime label for the bill (default: command basename)",
    )
    parser.add_argument(
        "--heartbeat", default=str(default_root / "state" / "heartbeat.json")
    )
    parser.add_argument(
        "--bill", default=str(default_root / "ledger" / "sessions.jsonl")
    )
    parser.add_argument(
        "--job-memory-limit",
        type=int,
        default=None,
        help="hard commit cap for the whole tree (bytes); fails allocations, never kills",
    )
    parser.add_argument(
        "--notify-limit",
        type=int,
        default=None,
        help="soft threshold (bytes): warn once when the tree's peak crosses it",
    )
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument(
        "--force",
        action="store_true",
        help="launch even when the gate refuses (recorded in the bill)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the admission verdict and exit"
    )
    args = parser.parse_args(own)
    if not command:
        parser.print_usage(sys.stderr)
        _stderr("no command given after `--`")
        return EXIT_USAGE

    verdict = decide(read_heartbeat(args.heartbeat), now=now(), force=args.force)
    for warning in verdict.warnings:
        _stderr(f"warning: {warning}")
    if args.dry_run:
        print(f"{'ADMIT' if verdict.admit else 'REFUSE'}: {verdict.reason}")
        return 0
    if not verdict.admit:
        _stderr(
            f"REFUSED: {verdict.reason}. {verdict.hint}. Re-run with --force to launch anyway."
        )
        return EXIT_REFUSED

    runtime = args.runtime or _basename(command[0])
    job = None
    try:
        job = job_factory(args.job_memory_limit)
        if not job.assign_current():
            _stderr(
                "warning: could not assign this process to a job object; running without a job object"
            )
            job.close()
            job = None
    except OSError as exc:
        _stderr(
            f"warning: job object unavailable ({exc}); running without a job object"
        )
        job = None

    started = now()
    started_wall = time.time()
    peak = 0
    warned_soft = False
    try:
        proc = subprocess.Popen(command)
    except (FileNotFoundError, OSError) as exc:
        _stderr(f"could not start {command[0]!r}: {exc}")
        exit_code = EXIT_NOT_FOUND
    else:
        while True:
            try:
                exit_code = proc.wait(timeout=args.poll_seconds)
                break
            except subprocess.TimeoutExpired:
                pass
            finally:
                if job is not None:
                    peak = max(peak, job.peak_bytes())
                    if (
                        args.notify_limit
                        and not warned_soft
                        and peak > args.notify_limit
                    ):
                        warned_soft = True
                        _stderr(
                            f"soft memory limit crossed: tree peak {peak / 2**20:.0f} MiB > {args.notify_limit / 2**20:.0f} MiB"
                        )
    duration = time.time() - started_wall
    if job is not None:
        peak = max(peak, job.peak_bytes())
        job.close()
    row = {
        "schema": "process-hygiene-session-v1",
        "ts_start": started,
        "ts_end": now(),
        "duration_seconds": round(duration, 3),
        "runtime": runtime,
        "command": command,
        "exit_code": exit_code,
        "job": job is not None,
        "job_memory_limit_bytes": args.job_memory_limit,
        "notify_limit_bytes": args.notify_limit,
        "peak_job_bytes": peak,
        "admitted": verdict.to_dict(),
    }
    _append_bill(args.bill, row)
    _stderr(
        f"{runtime} exited {exit_code} after {duration:.0f}s; peak job memory {peak / 2**20:.0f} MiB (bill: {args.bill})"
    )
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
