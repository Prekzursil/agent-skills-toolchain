#!/usr/bin/env python3
"""Two-signal process liveness: heartbeat age + CPU-time delta over 20s.

Windows port 2026-10-26 (shard21 w3): SIGSTOP maps to suspend via psutil;
CPU ticks come from GetProcessTimes in 100ns units. The POSIX /proc +
os.kill branch is unchanged and remains authoritative on Linux.

Idle-alive (no work output) must stay ALIVE. SIGSTOP must flip to HUNG.
Kill must flip again to DEAD. mtime is not a signal. Work-byte silence is
not a hang signal.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

ALIVE = "ALIVE"
HUNG = "HUNG"
DEAD = "DEAD"
UNDECIDABLE = "UNDECIDABLE"

WINDOW_S = 20.0
HB_STALE_S = 2.0
HB_PERIOD_S = 0.25
FORBIDDEN_SOURCES = frozenset(
    {"mtime", "mtime-only", "file-mtime", "st_mtime", "os.path.getmtime"}
)
HB_SOURCE = "heartbeat-age"
CPU_SOURCE = "cpu-time-delta"

# Windows signal module lacks SIGSTOP/SIGKILL/SIGCONT; keep the POSIX numbers
# so stop/kill semantics stay comparable across platforms.
SIGSTOP = getattr(signal, "SIGSTOP", 19)
SIGCONT = getattr(signal, "SIGCONT", 18)
SIGKILL = getattr(signal, "SIGKILL", 9)


@dataclass(frozen=True)
class Sample:
    pid: int
    pid_alive: bool
    proc_state: str | None
    heartbeat_t0: int
    heartbeat_t1: int
    heartbeat_age_s: float
    heartbeat_source: str
    cpu_t0: int | None
    cpu_t1: int | None
    cpu_delta: int | None
    cpu_source: str
    work_t0: int
    work_t1: int
    window_s: float
    planted: str


@dataclass(frozen=True)
class Verdict:
    verdict: str
    hang_fired: bool
    reason: str
    guessed: bool
    heartbeat_advancing: bool | None
    cpu_frozen: bool | None
    heartbeat_source: str
    cpu_source: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _subject_loop(hb_path: Path, work_path: Path) -> None:
    """Emit a monotonic heartbeat independently of work output.

    work_path is created and left empty: absence of work bytes is not a hang.
    """
    hb_path.parent.mkdir(parents=True, exist_ok=True)
    work_path.parent.mkdir(parents=True, exist_ok=True)
    if not work_path.exists():
        work_path.write_bytes(b"")
    hb_path.write_text("", encoding="utf-8")
    token = 0
    while True:
        token += 1
        rec = {
            "kind": "process-heartbeat",
            "mono_ns": time.monotonic_ns(),
            "pid": os.getpid(),
            "token": token,
        }
        with hb_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        time.sleep(HB_PERIOD_S)


def read_heartbeat(path: Path) -> tuple[int, int | None]:
    """Return (last_token, last_mono_ns). Never uses st_mtime."""
    if not path.is_file():
        return 0, None
    last_token = 0
    last_mono: int | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            last_token = int(rec["token"])
            last_mono = int(rec["mono_ns"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    return last_token, last_mono


def heartbeat_age_s(last_mono_ns: int | None) -> float:
    if last_mono_ns is None:
        return float("inf")
    return max(0.0, (time.monotonic_ns() - last_mono_ns) / 1_000_000_000.0)


IS_WINDOWS = os.name == "nt"


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


def classify(sample: Sample) -> Verdict:
    if (
        sample.heartbeat_source.strip().lower() in FORBIDDEN_SOURCES
        or sample.cpu_source.strip().lower() in FORBIDDEN_SOURCES
    ):
        return Verdict(
            verdict=UNDECIDABLE,
            hang_fired=False,
            reason="mtime-only-forbidden",
            guessed=False,
            heartbeat_advancing=None,
            cpu_frozen=None,
            heartbeat_source=sample.heartbeat_source,
            cpu_source=sample.cpu_source,
        )
    if not sample.pid_alive:
        return Verdict(
            verdict=DEAD,
            hang_fired=False,
            reason="process-gone",
            guessed=False,
            heartbeat_advancing=sample.heartbeat_t1 > sample.heartbeat_t0,
            cpu_frozen=None,
            heartbeat_source=sample.heartbeat_source,
            cpu_source=sample.cpu_source,
        )
    hb_adv = sample.heartbeat_t1 > sample.heartbeat_t0
    cpu_frozen = sample.cpu_delta == 0 if sample.cpu_delta is not None else None
    hb_stale = (not hb_adv) and sample.heartbeat_age_s >= HB_STALE_S
    if hb_adv:
        return Verdict(
            verdict=ALIVE,
            hang_fired=False,
            reason="heartbeat-advancing-independent-of-work",
            guessed=False,
            heartbeat_advancing=True,
            cpu_frozen=cpu_frozen,
            heartbeat_source=sample.heartbeat_source,
            cpu_source=sample.cpu_source,
        )
    if hb_stale and cpu_frozen is True:
        return Verdict(
            verdict=HUNG,
            hang_fired=True,
            reason="heartbeat-stale-and-cpu-frozen",
            guessed=False,
            heartbeat_advancing=False,
            cpu_frozen=True,
            heartbeat_source=sample.heartbeat_source,
            cpu_source=sample.cpu_source,
        )
    if hb_stale and cpu_frozen is False:
        return Verdict(
            verdict=UNDECIDABLE,
            hang_fired=False,
            reason="heartbeat-stale-cpu-still-advancing-do-not-guess",
            guessed=False,
            heartbeat_advancing=False,
            cpu_frozen=False,
            heartbeat_source=sample.heartbeat_source,
            cpu_source=sample.cpu_source,
        )
    return Verdict(
        verdict=UNDECIDABLE,
        hang_fired=False,
        reason="insufficient-two-signal-evidence",
        guessed=False,
        heartbeat_advancing=hb_adv,
        cpu_frozen=cpu_frozen,
        heartbeat_source=sample.heartbeat_source,
        cpu_source=sample.cpu_source,
    )


def work_silence_mutant(sample: Sample) -> str:
    """Single-signal defect: no work bytes ⇒ hung. Fires on idle-alive."""
    if not sample.pid_alive:
        return DEAD
    if sample.work_t1 <= sample.work_t0:
        return HUNG
    return ALIVE


def heartbeat_only_mutant(sample: Sample) -> str:
    """Single-signal defect: frozen heartbeat ⇒ HUNG even after kill."""
    if sample.heartbeat_t1 > sample.heartbeat_t0:
        return ALIVE
    return HUNG


def cpu_only_mutant(sample: Sample) -> str:
    """Single-signal defect: zero CPU ⇒ hung. Fires on a sleeping idle process."""
    if not sample.pid_alive:
        return DEAD
    if sample.cpu_delta == 0:
        return HUNG
    return ALIVE


def mtime_sample(base: Sample) -> Sample:
    return Sample(
        pid=base.pid,
        pid_alive=base.pid_alive,
        proc_state=base.proc_state,
        heartbeat_t0=base.heartbeat_t0,
        heartbeat_t1=base.heartbeat_t1,
        heartbeat_age_s=base.heartbeat_age_s,
        heartbeat_source="mtime",
        cpu_t0=base.cpu_t0,
        cpu_t1=base.cpu_t1,
        cpu_delta=base.cpu_delta,
        cpu_source="mtime",
        work_t0=base.work_t0,
        work_t1=base.work_t1,
        window_s=base.window_s,
        planted=base.planted,
    )


class Subject:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.hb_path = root / "heartbeat.jsonl"
        self.work_path = root / "work.bin"
        self.proc: subprocess.Popen[bytes] | None = None
        self.pid = 0

    def start(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.hb_path.write_text("", encoding="utf-8")
        self.work_path.write_bytes(b"")
        self.proc = subprocess.Popen(
            [sys.executable, "-B", str(HERE / "liveness.py"), "--subject", str(self.hb_path), str(self.work_path)],
            cwd=str(REPO),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.pid = int(self.proc.pid)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            token, _ = read_heartbeat(self.hb_path)
            if token >= 1 and pid_is_alive(self.pid):
                return
            time.sleep(0.05)
        raise RuntimeError("subject did not emit a heartbeat")

    def stop_signal(self, sig: int) -> None:
        if not self.pid:
            return
        if IS_WINDOWS:
            # os.kill would TerminateProcess; SIGSTOP means suspend here.
            if sig == SIGSTOP:
                _psutil().Process(self.pid).suspend()
                return
            if sig == SIGCONT:
                _psutil().Process(self.pid).resume()
                return
        os.kill(self.pid, sig)

    def kill(self) -> None:
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
        try:
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
        self.proc = None

    def sample_window(self, planted: str, window_s: float = WINDOW_S) -> Sample:
        t0_mono = time.monotonic()
        hb0, _ = read_heartbeat(self.hb_path)
        cpu0 = read_cpu_ticks(self.pid)
        work0 = self.work_path.stat().st_size if self.work_path.is_file() else 0
        time.sleep(window_s)
        hb1, mono1 = read_heartbeat(self.hb_path)
        cpu1 = read_cpu_ticks(self.pid)
        work1 = self.work_path.stat().st_size if self.work_path.is_file() else 0
        elapsed = time.monotonic() - t0_mono
        cpu_delta = None if cpu0 is None or cpu1 is None else cpu1 - cpu0
        return Sample(
            pid=self.pid,
            pid_alive=pid_is_alive(self.pid),
            proc_state=read_proc_state(self.pid),
            heartbeat_t0=hb0,
            heartbeat_t1=hb1,
            heartbeat_age_s=heartbeat_age_s(mono1),
            heartbeat_source=HB_SOURCE,
            cpu_t0=cpu0,
            cpu_t1=cpu1,
            cpu_delta=cpu_delta,
            cpu_source=CPU_SOURCE,
            work_t0=work0,
            work_t1=work1,
            window_s=elapsed,
            planted=planted,
        )


def _require_posix() -> None:
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


def pack_row(sample: Sample, verdict: Verdict) -> dict[str, Any]:
    row = asdict(sample)
    row["verdict"] = verdict.as_dict()
    row["work_bytes_unchanged"] = sample.work_t0 == sample.work_t1
    return row


def run_idle_then_sigstop_then_kill(tmp: Path, window_s: float = WINDOW_S) -> dict[str, Any]:
    """Both-states plus second flip: idle-alive → SIGSTOP hung → killed dead."""
    _require_posix()
    sub = Subject(tmp)
    idle_row: dict[str, Any] | None = None
    stop_row: dict[str, Any] | None = None
    dead_row: dict[str, Any] | None = None
    try:
        sub.start()
        idle = sub.sample_window("idle-alive", window_s=window_s)
        idle_v = classify(idle)
        idle_row = pack_row(idle, idle_v)

        sub.stop_signal(SIGSTOP)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and read_proc_state(sub.pid) != "T":
            time.sleep(0.01)
        if read_proc_state(sub.pid) != "T":
            raise RuntimeError(f"SIGSTOP did not reach state=T (got {read_proc_state(sub.pid)})")
        stopped = sub.sample_window("sigstop", window_s=window_s)
        stop_v = classify(stopped)
        stop_row = pack_row(stopped, stop_v)

        sub.kill()
        dead = Sample(
            pid=sub.pid,
            pid_alive=pid_is_alive(sub.pid),
            proc_state=read_proc_state(sub.pid),
            heartbeat_t0=stopped.heartbeat_t1,
            heartbeat_t1=read_heartbeat(sub.hb_path)[0],
            heartbeat_age_s=heartbeat_age_s(read_heartbeat(sub.hb_path)[1]),
            heartbeat_source=HB_SOURCE,
            cpu_t0=stopped.cpu_t1,
            cpu_t1=read_cpu_ticks(sub.pid),
            cpu_delta=None,
            cpu_source=CPU_SOURCE,
            work_t0=stopped.work_t1,
            work_t1=sub.work_path.stat().st_size if sub.work_path.is_file() else 0,
            window_s=0.0,
            planted="killed",
        )
        dead_v = classify(dead)
        dead_row = pack_row(dead, dead_v)
    finally:
        try:
            if sub.proc is not None:
                try:
                    if IS_WINDOWS:
                        _psutil().Process(sub.pid).resume()
                    else:
                        os.kill(sub.pid, SIGCONT)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
                sub.kill()
        except Exception:
            pass

    assert idle_row and stop_row and dead_row
    idle_v = Verdict(**idle_row["verdict"])
    stop_v = Verdict(**stop_row["verdict"])
    dead_v = Verdict(**dead_row["verdict"])
    idle_sample = _sample_from_row(idle_row)
    return {
        "window_s_requested": window_s,
        "idle": idle_row,
        "sigstop": stop_row,
        "killed": dead_row,
        "sequence": [idle_v.verdict, stop_v.verdict, dead_v.verdict],
        "flipped_on_sigstop": idle_v.verdict == ALIVE and stop_v.verdict == HUNG,
        "flipped_on_kill": stop_v.verdict == HUNG and dead_v.verdict == DEAD,
        "detector_silent_idle": idle_v.verdict == ALIVE and idle_v.hang_fired is False,
        "detector_fires_sigstop": stop_v.hang_fired is True and stop_v.verdict == HUNG,
        "work_independent_idle": idle_row["work_bytes_unchanged"] is True
        and idle_row["work_t0"] == 0
        and idle_row["work_t1"] == 0,
        "work_silence_mutant_fires_on_idle": work_silence_mutant(idle_sample) == HUNG,
        "heartbeat_only_mutant_after_kill": heartbeat_only_mutant(_sample_from_row(dead_row)),
        "mtime_idle": classify(mtime_sample(idle_sample)).as_dict(),
    }


def run_known_alive_then_kill(tmp: Path, window_s: float = WINDOW_S) -> dict[str, Any]:
    """Detector control: ALIVE on a known-running process before any DEAD."""
    _require_posix()
    sub = Subject(tmp)
    alive_row: dict[str, Any] | None = None
    dead_row: dict[str, Any] | None = None
    try:
        sub.start()
        if not pid_is_alive(sub.pid):
            raise RuntimeError("known-running control process is not alive")
        alive = sub.sample_window("known-running", window_s=window_s)
        alive_v = classify(alive)
        alive_row = pack_row(alive, alive_v)
        if alive_v.verdict != ALIVE:
            raise RuntimeError(f"refusing DEAD/HUNG: known-running classified {alive_v.verdict}")
        # Baseline AT kill time, not sample end: a running subject may flush
        # one more heartbeat between sample end and kill, which would make
        # the heartbeat-only mutant misread death as ALIVE.
        hb_at_kill = read_heartbeat(sub.hb_path)[0]
        sub.kill()
        dead = Sample(
            pid=sub.pid,
            pid_alive=pid_is_alive(sub.pid),
            proc_state=read_proc_state(sub.pid),
            heartbeat_t0=hb_at_kill,
            heartbeat_t1=read_heartbeat(sub.hb_path)[0],
            heartbeat_age_s=heartbeat_age_s(read_heartbeat(sub.hb_path)[1]),
            heartbeat_source=HB_SOURCE,
            cpu_t0=alive.cpu_t1,
            cpu_t1=read_cpu_ticks(sub.pid),
            cpu_delta=None,
            cpu_source=CPU_SOURCE,
            work_t0=alive.work_t1,
            work_t1=sub.work_path.stat().st_size if sub.work_path.is_file() else 0,
            window_s=0.0,
            planted="killed",
        )
        dead_v = classify(dead)
        dead_row = pack_row(dead, dead_v)
    finally:
        try:
            if sub.proc is not None:
                sub.kill()
        except Exception:
            pass

    assert alive_row and dead_row
    alive_v = Verdict(**alive_row["verdict"])
    dead_v = Verdict(**dead_row["verdict"])
    return {
        "window_s_requested": window_s,
        "known_running": alive_row,
        "killed": dead_row,
        "alive_before_dead": alive_v.verdict == ALIVE and dead_v.verdict == DEAD,
        "trusted_dead": alive_v.verdict == ALIVE,
        "heartbeat_only_mutant_after_kill": heartbeat_only_mutant(_sample_from_row(dead_row)),
        "sequence": [alive_v.verdict, dead_v.verdict],
    }


def _sample_from_row(row: dict[str, Any]) -> Sample:
    skip = {"verdict", "work_bytes_unchanged"}
    fields = {k: row[k] for k in Sample.__dataclass_fields__ if k not in skip}
    return Sample(**fields)


def campaign(tmp: Path | None = None) -> dict[str, Any]:
    import tempfile

    def _run(root: Path) -> dict[str, Any]:
        both = run_idle_then_sigstop_then_kill(root / "both")
        ctrl = run_known_alive_then_kill(root / "control")
        ok = (
            both["detector_silent_idle"]
            and both["detector_fires_sigstop"]
            and both["flipped_on_sigstop"]
            and both["flipped_on_kill"]
            and both["work_independent_idle"]
            and both["work_silence_mutant_fires_on_idle"]
            and both["heartbeat_only_mutant_after_kill"] == HUNG
            and ctrl["alive_before_dead"]
            and ctrl["trusted_dead"]
            and ctrl["heartbeat_only_mutant_after_kill"] == HUNG
            and both["mtime_idle"]["verdict"] == UNDECIDABLE
            and both["idle"]["window_s"] >= WINDOW_S - 0.5
            and both["sigstop"]["window_s"] >= WINDOW_S - 0.5
            and ctrl["known_running"]["window_s"] >= WINDOW_S - 0.5
        )
        return {"ok": ok, "both_states": both, "detector_control": ctrl}

    if tmp is not None:
        return _run(tmp)
    with tempfile.TemporaryDirectory(prefix="tst0151-") as td:
        return _run(Path(td))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--subject"]:
        _subject_loop(Path(argv[1]), Path(argv[2]))
        return 0
    table = campaign()
    print(json.dumps({"ok": table["ok"], "sequence_both": table["both_states"]["sequence"], "sequence_ctrl": table["detector_control"]["sequence"]}, sort_keys=True))
    print("SUCCESS:TST-0151" if table["ok"] else "FAILED:TST-0151")
    return 0 if table["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
