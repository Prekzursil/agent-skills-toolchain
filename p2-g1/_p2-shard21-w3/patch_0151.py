#!/usr/bin/env python3
"""Shard 21 wave 3: port TST-0151 liveness.py to Windows (psutil backend).

POSIX /proc + SIGSTOP branch is preserved verbatim for Linux review parity.
Windows branch: psutil for state/cpu/suspend/kill; GetProcessTimes-derived
cpu ticks keep the exact 100ns-tick semantics of /proc utime+stime.
"""
from pathlib import Path

P = Path.home() / "p2-g1" / "command-center" / "p2-wave" / "probes" / "TST-0151" / "liveness.py"
src = P.read_text(encoding="utf-8")

# 1) read_cpu_ticks / read_proc_state / pid_is_alive: platform-branched
old_cpu = '''def read_cpu_ticks(pid: int) -> int | None:
    path = Path(f"/proc/{pid}/stat")
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        return None
    close = text.rfind(")")
    if close < 0:
        return None
    rest = text[close + 1 :].split()
    if len(rest) < 15:
        return None
    # field 14 utime, field 15 stime; after comm, field 3 is rest[0]
    utime = int(rest[13 - 3])
    stime = int(rest[14 - 3])
    return utime + stime


def read_proc_state(pid: int) -> str | None:
    path = Path(f"/proc/{pid}/stat")
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        return None
    close = text.rfind(")")
    if close < 0:
        return None
    rest = text[close + 1 :].split()
    if not rest:
        return None
    return rest[0]


def pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    state = read_proc_state(pid)
    if state is None:
        return False
    if state == "Z":
        return False
    return True
'''
new_cpu = '''IS_WINDOWS = os.name == "nt"


def _psutil():
    import psutil  # deferred: POSIX review shells may not ship it

    return psutil


# psutil status -> the single-letter state the /proc branch reports.
_PSUTIL_STATE = {
    "running": "R",
    "sleeping": "S",
    "disk-sleep": "D",
    "stopped": "T",
    "tracing-stop": "T",
    "zombie": "Z",
    "dead": "Z",
    "idle": "I",
    "locked": "L",
    "waiting": "W",
    "suspended": "T",
}


def read_cpu_ticks(pid: int) -> int | None:
    if IS_WINDOWS:
        # GetProcessTimes user+system in 100ns ticks, the same quantity
        # /proc/<pid>/stat fields 14+15 report in clock ticks.
        try:
            times = _psutil().Process(pid).cpu_times()
        except Exception:
            return None
        return int(round((times.user + times.system) * 10_000_000))
    path = Path(f"/proc/{pid}/stat")
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        return None
    close = text.rfind(")")
    if close < 0:
        return None
    rest = text[close + 1 :].split()
    if len(rest) < 15:
        return None
    # field 14 utime, field 15 stime; after comm, field 3 is rest[0]
    utime = int(rest[13 - 3])
    stime = int(rest[14 - 3])
    return utime + stime


def read_proc_state(pid: int) -> str | None:
    if IS_WINDOWS:
        try:
            status = _psutil().Process(pid).status()
        except Exception:
            return None
        return _PSUTIL_STATE.get(str(status))
    path = Path(f"/proc/{pid}/stat")
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        return None
    close = text.rfind(")")
    if close < 0:
        return None
    rest = text[close + 1 :].split()
    if not rest:
        return None
    return rest[0]


def pid_is_alive(pid: int) -> bool:
    if IS_WINDOWS:
        # os.kill(pid, 0) is TerminateProcess on Windows - never use it as a
        # liveness probe there. psutil opens with query access only.
        try:
            proc = _psutil().Process(pid)
        except Exception:
            return False
        try:
            return proc.status() != "zombie"
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    state = read_proc_state(pid)
    if state is None:
        return False
    if state == "Z":
        return False
    return True
'''
assert old_cpu in src, "cpu block not found"
src = src.replace(old_cpu, new_cpu)

# 2) _require_posix -> platform gate
old_gate = '''def _require_posix() -> None:
    if os.name != "posix" or not hasattr(signal, "SIGSTOP"):
        raise RuntimeError("SIGSTOP liveness probe requires POSIX")
    if not Path("/proc/self/stat").is_file():
        raise RuntimeError("/proc is required for CPU-time delta")
'''
new_gate = '''def _require_posix() -> None:
    if IS_WINDOWS:
        try:
            _psutil()
        except Exception as exc:  # pragma: no cover - env guard
            raise RuntimeError(f"Windows liveness probe requires psutil: {exc}")
        return
    if os.name != "posix" or not hasattr(signal, "SIGSTOP"):
        raise RuntimeError("SIGSTOP liveness probe requires POSIX")
    if not Path("/proc/self/stat").is_file():
        raise RuntimeError("/proc is required for CPU-time delta")
'''
assert old_gate in src, "gate not found"
src = src.replace(old_gate, new_gate)

# 3) Subject.stop_signal: suspend/resume on Windows
old_stop = '''    def stop_signal(self, sig: int) -> None:
        if self.pid:
            os.kill(self.pid, sig)
'''
new_stop = '''    def stop_signal(self, sig: int) -> None:
        if not self.pid:
            return
        if IS_WINDOWS:
            # os.kill would TerminateProcess; SIGSTOP means suspend here.
            if sig == getattr(signal, "SIGSTOP", None):
                _psutil().Process(self.pid).suspend()
                return
            if sig == getattr(signal, "SIGCONT", None):
                _psutil().Process(self.pid).resume()
                return
        os.kill(self.pid, sig)
'''
assert old_stop in src, "stop_signal not found"
src = src.replace(old_stop, new_stop)

# 4) Subject.kill: psutil kill on Windows
old_kill = '''    def kill(self) -> None:
        if self.proc is None:
            return
        try:
            os.kill(self.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
'''
new_kill = '''    def kill(self) -> None:
        if self.proc is None:
            return
        if IS_WINDOWS:
            try:
                _psutil().Process(self.pid).kill()
            except Exception:
                pass
        else:
            try:
                os.kill(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
'''
assert old_kill in src, "kill not found"
src = src.replace(old_kill, new_kill)

# 5) finally-block SIGCONT in run_idle_then_sigstop_then_kill
old_cont = '''        try:
            if sub.proc is not None:
                try:
                    os.kill(sub.pid, signal.SIGCONT)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
                sub.kill()
        except Exception:
            pass
'''
new_cont = '''        try:
            if sub.proc is not None:
                try:
                    if IS_WINDOWS:
                        _psutil().Process(sub.pid).resume()
                    else:
                        os.kill(sub.pid, signal.SIGCONT)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
                sub.kill()
        except Exception:
            pass
'''
assert old_cont in src, "sigcont finally not found"
src = src.replace(old_cont, new_cont)

# 6) retry loop in kill(): second SIGKILL guarded
old_retry = '''        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.kill(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.proc.wait(timeout=5)
'''
new_retry = '''        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                if IS_WINDOWS:
                    _psutil().Process(self.pid).kill()
                else:
                    os.kill(self.pid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
            except Exception:
                pass
            self.proc.wait(timeout=5)
'''
assert old_retry in src, "kill retry not found"
src = src.replace(old_retry, new_retry)

# 7) module docstring note
marker = '"""Two-signal process liveness: heartbeat age + CPU-time delta over 20s.'
src = src.replace(
    marker,
    marker
    + "\n\nWindows port 2026-10-26 (shard21 w3): SIGSTOP maps to suspend via psutil;\n"
      "CPU ticks come from GetProcessTimes in 100ns units. The POSIX /proc +\n"
      "os.kill branch is unchanged and remains authoritative on Linux.",
    1,
)

P.write_text(src, encoding="utf-8", newline="\n")
print("patched", P)
