"""Executed fault scenarios for BLD-0027 (real processes, not source reads)."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402
import naive_mtime as N  # noqa: E402

WORKER = HERE / "worker.py"
STALL_WINDOW_S = 0.4
PYTHON = sys.executable


def cpu_ticks(pid: int) -> int | None:
    path = Path(f"/proc/{pid}/stat")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    rparen = text.rfind(")")
    if rparen < 0:
        return None
    rest = text[rparen + 2 :].split()
    if len(rest) < 13:
        return None
    return int(rest[11]) + int(rest[12])


def cpu_from_file(path: Path) -> float | None:
    try:
        return float(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def heartbeat_value(path: Path) -> int:
    try:
        return int(path.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        return 0


def alive(proc: subprocess.Popen[Any] | None) -> bool:
    return proc is not None and proc.poll() is None


def stop_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".stop")


def clear_stop(path: Path) -> None:
    sp = stop_path(path)
    if sp.exists():
        sp.unlink()


def request_stop(path: Path) -> None:
    stop_path(path).write_text("1", encoding="utf-8")


def kill_proc(proc: subprocess.Popen[Any] | None, sig: int = signal.SIGKILL) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        os.kill(proc.pid, sig)
    except OSError:
        pass
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)


def spawn(mode: str, path: Path, cpu: Path | None = None) -> subprocess.Popen[Any]:
    clear_stop(path)
    args = [PYTHON, "-B", str(WORKER), mode, str(path)]
    if cpu is not None:
        args.append(str(cpu))
    return subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def sample(
    work: subprocess.Popen[Any] | None,
    artifact: Path,
    cpu_path: Path,
    heartbeat: Path | None,
    interval: float,
) -> dict[str, int]:
    pid = work.pid if work is not None and work.poll() is None else None
    t1 = cpu_ticks(pid) if pid else None
    p1 = cpu_from_file(cpu_path)
    b1 = file_size(artifact)
    h1 = heartbeat_value(heartbeat) if heartbeat is not None else 0
    time.sleep(interval)
    t2 = cpu_ticks(pid) if pid else None
    p2 = cpu_from_file(cpu_path)
    b2 = file_size(artifact)
    h2 = heartbeat_value(heartbeat) if heartbeat is not None else 0
    ticks = 0
    if t1 is not None and t2 is not None:
        ticks = max(0, t2 - t1)
    if ticks == 0 and p1 is not None and p2 is not None and p2 > p1:
        ticks = max(1, int((p2 - p1) * 1000))
    return {
        "cpu_delta": ticks,
        "byte_delta": max(0, b2 - b1),
        "heartbeat_delta": max(0, h2 - h1),
    }


def executed_timeout() -> dict[str, Any]:
    try:
        subprocess.run(
            [PYTHON, "-c", "import time; time.sleep(8)"],
            timeout=0.2,
            capture_output=True,
            check=False,
        )
        timed_out = False
        exit_code = 0
    except subprocess.TimeoutExpired:
        timed_out = True
        exit_code = 124
    obs = C.Observation(timed_out=timed_out, exit_code=exit_code, artifact_exists=False)
    honest = C.classify(obs)
    naive = N.classify_mtime_only(obs)
    return {
        "id": "T-TIMEOUT-FAILED",
        "timed_out": timed_out,
        "honest": honest,
        "naive": naive,
        "pass": timed_out and honest == C.FAILED and honest != C.SUCCESS,
        "naive_caught": naive == C.SUCCESS,
    }


def executed_exit0_missing(work_dir: Path) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    artifact = work_dir / "missing-artifact.bin"
    proc = spawn("exit0-missing", artifact)
    rc = proc.wait(timeout=5)
    exists = artifact.is_file() and artifact.stat().st_size > 0
    obs = C.Observation(exit_code=rc, artifact_exists=exists)
    honest = C.classify(obs)
    naive = N.classify_mtime_only(obs)
    return {
        "id": "T-EXIT0-MISSING-FAILED",
        "exit_code": rc,
        "artifact_exists": exists,
        "honest": honest,
        "naive": naive,
        "pass": rc == 0 and not exists and honest == C.FAILED,
        "naive_caught": naive == C.SUCCESS,
    }


def executed_finished_11h(work_dir: Path) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    artifact = work_dir / "finished-agent.bin"
    artifact.write_bytes(b"done")
    age = 11 * 3600
    now = time.time()
    os.utime(artifact, (now - age, now - age))
    mtime_age = time.time() - artifact.stat().st_mtime
    obs = C.Observation(
        exit_code=0,
        artifact_exists=True,
        cpu_delta=0,
        byte_delta=0,
        heartbeat_delta=0,
        work_alive=False,
        orchestrator_state=C.ORCH_FINISHED,
        mtime_age_s=mtime_age,
        stall_window_s=STALL_WINDOW_S,
    )
    honest = C.classify(obs)
    naive = N.classify_mtime_only(obs)
    return {
        "id": "T-FINISHED-11H-NOT-STALL",
        "mtime_age_s": mtime_age,
        "honest": honest,
        "naive": naive,
        "pass": mtime_age >= 10 * 3600 and honest == C.FINISHED and not C.is_stalled(honest),
        "naive_caught": naive == C.STALLED,
    }


def executed_freeze_quiet(work_dir: Path) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    artifact = work_dir / "quiet.bin"
    cpu_path = work_dir / "quiet.cpu"
    hb = work_dir / "quiet.hb"
    work = spawn("quiet", artifact, cpu_path)
    mon = spawn("heartbeat", hb)
    try:
        time.sleep(0.25)
        samp = sample(work, artifact, cpu_path, hb, interval=2 * STALL_WINDOW_S)
        obs = C.Observation(
            cpu_delta=samp["cpu_delta"],
            byte_delta=samp["byte_delta"],
            heartbeat_delta=samp["heartbeat_delta"],
            work_alive=alive(work),
            monitor_pid_alive=alive(mon),
            orchestrator_state=C.ORCH_RUNNING,
            stall_window_s=STALL_WINDOW_S,
            artifact_exists=artifact.is_file(),
        )
        honest = C.classify(obs)
        return {
            "id": "T-FREEZE-NOT-STALLED",
            "cpu_delta": samp["cpu_delta"],
            "byte_delta": samp["byte_delta"],
            "heartbeat_delta": samp["heartbeat_delta"],
            "honest": honest,
            "pass": (
                alive(work)
                and samp["cpu_delta"] > 0
                and samp["byte_delta"] == 0
                and not C.is_stalled(honest)
                and honest in {C.ALIVE_QUIET, C.UNDECIDABLE}
            ),
        }
    finally:
        request_stop(artifact)
        request_stop(hb)
        kill_proc(work)
        kill_proc(mon)


def executed_severed(work_dir: Path, *, mechanism: str) -> dict[str, Any]:
    """SIGKILL the monitor, or SIGKILL only the heartbeat relay (partition)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    artifact = work_dir / f"sev-{mechanism}.bin"
    cpu_path = work_dir / f"sev-{mechanism}.cpu"
    hb_pub = work_dir / f"sev-{mechanism}.hb"
    hb_priv = work_dir / f"sev-{mechanism}.hb.priv"
    work = spawn("grow", artifact, cpu_path)
    monitor_target = hb_priv if mechanism == "partition" else hb_pub
    monitor = spawn("heartbeat", monitor_target)
    relay: subprocess.Popen[Any] | None = None
    relay_stop = hb_pub.with_name(hb_pub.name + ".relay-stop")
    if mechanism == "partition":
        relay_py = (
            "import time, pathlib\n"
            f"src=pathlib.Path({str(hb_priv)!r})\n"
            f"dst=pathlib.Path({str(hb_pub)!r})\n"
            f"stop=pathlib.Path({str(relay_stop)!r})\n"
            "while not stop.exists():\n"
            "    if src.exists():\n"
            "        dst.write_bytes(src.read_bytes())\n"
            "    time.sleep(0.03)\n"
        )
        relay = subprocess.Popen(
            [PYTHON, "-c", relay_py],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    try:
        time.sleep(0.35)
        before = sample(work, artifact, cpu_path, hb_pub, interval=0.25)
        if mechanism == "sigkill":
            kill_proc(monitor, signal.SIGKILL)
            monitor = None
        elif mechanism == "partition":
            kill_proc(relay, signal.SIGKILL)
            relay = None
        else:
            raise ValueError(mechanism)
        time.sleep(0.15)
        after = sample(work, artifact, cpu_path, hb_pub, interval=0.35)
        obs = C.Observation(
            cpu_delta=after["cpu_delta"],
            byte_delta=after["byte_delta"],
            heartbeat_delta=after["heartbeat_delta"],
            work_alive=alive(work),
            monitor_pid_alive=alive(monitor),
            orchestrator_state=C.ORCH_RUNNING,
            artifact_exists=artifact.is_file() and file_size(artifact) > 0,
        )
        honest = C.classify(obs)
        return {
            "id": f"T-SEVERED-{mechanism.upper()}",
            "mechanism": mechanism,
            "before": before,
            "after": after,
            "work_alive": alive(work),
            "honest": honest,
            "pass": (
                alive(work)
                and after["cpu_delta"] > 0
                and after["byte_delta"] > 0
                and after["heartbeat_delta"] == 0
                and honest == C.SEVERED
                and honest != C.SUCCESS
            ),
        }
    finally:
        request_stop(artifact)
        request_stop(hb_pub)
        request_stop(hb_priv)
        relay_stop.write_text("1", encoding="utf-8")
        kill_proc(work)
        kill_proc(monitor)
        kill_proc(relay)


def run_catalog_faults(work_dir: Path | None = None) -> dict[str, Any]:
    (HERE / "_work").mkdir(parents=True, exist_ok=True)
    root = (
        Path(work_dir)
        if work_dir is not None
        else Path(tempfile.mkdtemp(prefix="cat-", dir=str(HERE / "_work")))
    )
    root.mkdir(parents=True, exist_ok=True)
    timeout = executed_timeout()
    missing = executed_exit0_missing(root / "missing")
    finished = executed_finished_11h(root / "finished")
    quiet = executed_freeze_quiet(root / "quiet")
    sev_kill = executed_severed(root / "sev-kill", mechanism="sigkill")
    sev_part = executed_severed(root / "sev-part", mechanism="partition")
    rows = [timeout, missing, finished, quiet, sev_kill, sev_part]
    return {
        "stall_window_s": STALL_WINDOW_S,
        "rows": rows,
        "all_pass": all(bool(r.get("pass")) for r in rows),
        "naive_timeout_caught": bool(timeout.get("naive_caught")),
        "naive_missing_caught": bool(missing.get("naive_caught")),
        "naive_11h_caught": bool(finished.get("naive_caught")),
    }


def main() -> int:
    report = run_catalog_faults()
    failed = [r["id"] for r in report["rows"] if not r.get("pass")]
    print(
        "all_pass={0} failed={1} naive_timeout={2} naive_11h={3}".format(
            report["all_pass"],
            failed,
            report["naive_timeout_caught"],
            report["naive_11h_caught"],
        )
    )
    for row in report["rows"]:
        print(f"{row['id']} pass={row.get('pass')} honest={row.get('honest')}")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
