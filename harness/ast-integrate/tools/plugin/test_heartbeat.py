"""IMP-0058: a live-but-slow operation is distinguishable from a hung one.

Every test spawns a real child and watches it with two independent liveness
signals over the same interval:

* the heartbeat *progress token* -- :class:`heartbeat.Heartbeat` is stamped
  only when the child shows evidence of progress (CPU ticks advanced in
  ``/proc/<pid>/stat`` or captured output grew), so the token is monotonic and
  freezes exactly when the child stops doing anything;
* the process-level signal itself -- CPU ticks summed over the child's process
  tree, or captured output bytes.

The verdict comes from :func:`heartbeat.classify_child`: a child whose token,
CPU and output all stayed flat for the whole hang window is ``FAILED`` (we
report it as ``HUNG``); a child that exited 0 with progress observed is
``SUCCESS``.  Absence of output is never itself evidence of a hang -- the
silent CPU-bound child below must classify as live.  File mtimes are never
consulted, and the last test proves that statically for the engine, the plugin
entry point and both ``scripts/longrun.*`` wrappers.

Each ``test_*`` asserts its invariants and returns the measurement dict the
IMP-0058 probes serialise; ``python3 test_heartbeat.py`` runs all five.
"""
from __future__ import annotations

import json
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

try:
    from . import heartbeat as hb_engine
    from . import longrun as longrun_entry
except ImportError:  # imported as a top-level module (the probes put tools/plugin on sys.path)
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import heartbeat as hb_engine
    import longrun as longrun_entry

LONGRUN_SCRIPTS = ("scripts/longrun.sh", "scripts/longrun.ps1")
CLASSIFIER_FILES = (
    "tools/plugin/heartbeat.py",
    "tools/plugin/longrun.py",
    "scripts/longrun.sh",
    "scripts/longrun.ps1",
)
# Any of these in a hang path would make the classifier infer liveness from a file timestamp.
MTIME_PATTERNS = (
    r"\bst_mtime\b",
    r"\bgetmtime\b",
    r"\bLastWriteTime\b",
    r"\bmtime\b",
    r"(^|\s)-(nt|ot)\s",
    r"\bstat\s+-c\s+['\"]?%[YZ]",
    r"\bfind\b.*\s-newer\b",
)

__all__ = [
    "observe_child",
    "test_hung_child_reports_failed_not_success",
    "test_longrun_scripts_reused",
    "test_mtime_not_consulted_in_classifier",
    "test_silence_is_not_hang",
    "test_token_advances_during_a_slow_op",
]


# ---------------------------------------------------------------------------
# /proc signals (independent of the heartbeat)
# ---------------------------------------------------------------------------


def _read_stat(pid: int) -> list[str] | None:
    try:
        text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    # comm may contain spaces; everything after the last ')' is fixed-format.
    head, _, tail = text.rpartition(")")
    fields = tail.split()
    return [head, *fields] if fields else None


def proc_state(pid: int) -> str | None:
    fields = _read_stat(pid)
    return fields[1] if fields and len(fields) > 1 else None


def _proc_cpu_ticks(pid: int) -> int:
    """utime + stime of one task in clock ticks (fields 14 and 15 of /proc/<pid>/stat)."""
    fields = _read_stat(pid)
    if not fields or len(fields) < 13:
        return 0
    # fields[0] is the '(comm' prefix, fields[1] is state == stat field 3, so
    # stat field N (1-based) is fields[N - 2] for N >= 3.
    return int(fields[14 - 2]) + int(fields[15 - 2])


def _children(pid: int) -> list[int]:
    kids: list[int] = []
    try:
        for entry in Path(f"/proc/{pid}/task").iterdir():
            text = (entry / "children").read_text(encoding="utf-8")
            kids.extend(int(tok) for tok in text.split())
        return kids
    except OSError:
        pass
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        fields = _read_stat(int(entry.name))
        if fields and len(fields) > 2 and fields[2] == str(pid):
            kids.append(int(entry.name))
    return kids


def tree_cpu_ticks(pid: int) -> int:
    """CPU ticks of ``pid`` plus every live descendant (a wrapper's real work is in its children)."""
    total = 0
    seen: set[int] = set()
    stack = [pid]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        total += _proc_cpu_ticks(cur)
        stack.extend(_children(cur))
    return total


# ---------------------------------------------------------------------------
# The observed run
# ---------------------------------------------------------------------------


def observe_child(
    argv: Sequence[str],
    *,
    hang_timeout_sec: float,
    poll_sec: float = 0.05,
    max_sec: float = 60.0,
    stop_after_spawn: bool = False,
    via_longrun_script: bool = False,
) -> dict[str, Any]:
    """Run ``argv`` and classify it from the progress token and the /proc CPU signal.

    ``stop_after_spawn`` sends SIGSTOP to the child immediately after spawn to
    manufacture a genuinely hung child (no ticks, no output, never exits).
    """
    hb = hb_engine.Heartbeat(hang_timeout_sec=hang_timeout_sec)
    started = time.monotonic()
    proc = subprocess.Popen(list(argv), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if stop_after_spawn:
        proc.send_signal(signal.SIGSTOP)
    out = bytearray()
    lock = threading.Lock()

    def _pump() -> None:
        assert proc.stdout is not None
        for chunk in iter(lambda: proc.stdout.read1(65536), b""):
            with lock:
                out.extend(chunk)

    pump = threading.Thread(target=_pump, daemon=True)
    pump.start()

    token_start = hb.token
    cpu_start = tree_cpu_ticks(proc.pid)
    cpu_last = cpu_start
    bytes_last = 0
    last_advance = started
    token_at_last_advance = hb.token
    cpu_at_last_advance = cpu_start
    bytes_at_last_advance = 0
    states_seen: set[str] = set()
    hang_window: dict[str, Any] | None = None
    killed_for_hang = False
    rc: int | None = None

    while True:
        rc = proc.poll()
        now = time.monotonic()
        if rc is None:
            state = proc_state(proc.pid)
            if state:
                states_seen.add(state)
            cpu_now = tree_cpu_ticks(proc.pid)
        else:
            cpu_now = cpu_last
        with lock:
            bytes_now = len(out)
        if cpu_now > cpu_last or bytes_now > bytes_last:
            hb.stamp(bytes_now)
            last_advance = now
            token_at_last_advance = hb.token
            cpu_at_last_advance = cpu_now
            bytes_at_last_advance = bytes_now
            cpu_last, bytes_last = cpu_now, bytes_now
        if rc is not None:
            break
        if hang_timeout_sec > 0 and (now - last_advance) >= hang_timeout_sec:
            hang_window = {
                "seconds": round(now - last_advance, 3),
                "token_delta": hb.token - token_at_last_advance,
                "cpu_delta": cpu_now - cpu_at_last_advance,
                "output_bytes_delta": bytes_now - bytes_at_last_advance,
                "child_state": proc_state(proc.pid),
            }
            killed_for_hang = True
            proc.kill()
            rc = proc.wait(timeout=10)
            break
        if now - started > max_sec:
            proc.kill()
            rc = proc.wait(timeout=10)
            break
        time.sleep(poll_sec)

    pump.join(timeout=2)
    elapsed = time.monotonic() - started
    token_end = hb.token
    cpu_delta = cpu_last - cpu_start
    output_bytes_delta = len(out)

    if killed_for_hang and hang_window is not None:
        verdict = hb_engine.classify_child(
            token_delta=hang_window["token_delta"],
            cpu_delta=hang_window["cpu_delta"],
            output_bytes_delta=hang_window["output_bytes_delta"],
            hang_timeout_sec=hang_timeout_sec,
            elapsed_sec=hang_window["seconds"],
        )
        classification = "HUNG" if verdict == "FAILED" else verdict
        status = "FAILED"
    else:
        verdict = hb_engine.classify_child(
            token_delta=token_end - token_start,
            cpu_delta=cpu_delta,
            output_bytes_delta=output_bytes_delta,
            hang_timeout_sec=hang_timeout_sec,
            elapsed_sec=elapsed,
        )
        if rc == 0:
            status = "SUCCESS"
            classification = "LIVE" if verdict == "RUNNING" else verdict
        else:
            status = "FAILED"
            classification = f"EXIT-{rc}"

    return {
        "argv": [str(a) for a in argv],
        "status": status,
        "classification": classification,
        "exit_code": rc,
        "token_start": token_start,
        "token_end": token_end,
        "token_advanced": token_end > token_start,
        "cpu_delta": cpu_delta,
        "output_bytes_delta": output_bytes_delta,
        "elapsed_sec": round(elapsed, 3),
        "hang_timeout_sec": hang_timeout_sec,
        "hang_window": hang_window,
        "child_states_seen": sorted(states_seen),
        "via_longrun_script": via_longrun_script,
        "mtime_consulted": False,
        "stdout_tail": bytes(out[-400:]).decode("utf-8", "replace"),
    }


def _busy_python(seconds: float, *, say: str | None = None) -> list[str]:
    """A CPU-bound child that prints nothing until (optionally) one final line."""
    tail = f"; print({say!r})" if say is not None else ""
    code = f"import time\nt = time.monotonic()\nwhile time.monotonic() - t < {seconds!r}:\n    pass{tail}"
    return [sys.executable, "-S", "-B", "-c", code]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_token_advances_during_a_slow_op() -> dict[str, Any]:
    """A CPU-bound op launched through scripts/longrun.sh advances the token and burns CPU ticks."""
    script = longrun_entry.longrun_script()
    assert script.is_file(), f"longrun wrapper missing: {script}"
    wrapped = [
        "bash",
        str(script),
        "-i",
        "imp0058-slow",
        "-h",
        "1",
        "-t",
        "0",
        "--",
        *_busy_python(1.2, say="slow-op-done"),
    ]
    rec = observe_child(wrapped, hang_timeout_sec=0, via_longrun_script=True)
    assert rec["status"] == "SUCCESS", rec
    assert rec["token_advanced"], rec
    assert rec["cpu_delta"] > 0, rec
    assert "SUCCESS:imp0058-slow" in rec["stdout_tail"], rec["stdout_tail"]
    rec["script"] = str(script.relative_to(REPO)).replace("\\", "/")
    return rec


def test_silence_is_not_hang() -> dict[str, Any]:
    """A silent CPU-bound child outlives the hang window: no output, yet classified live."""
    hang = 0.5
    rec = observe_child(_busy_python(1.2), hang_timeout_sec=hang)
    assert rec["output_bytes_delta"] == 0, rec
    assert rec["elapsed_sec"] > hang, rec
    assert rec["status"] == "SUCCESS", rec
    assert rec["classification"] == "LIVE", rec
    assert rec["token_advanced"] and rec["cpu_delta"] > 0, rec
    assert rec["hang_window"] is None, rec
    return rec


def test_hung_child_reports_failed_not_success() -> dict[str, Any]:
    """NEGATIVE CONTROL: a SIGSTOP'd child freezes token AND CPU; the runner says FAILED/HUNG."""
    hang = 0.8
    rec = observe_child(["sleep", "30"], hang_timeout_sec=hang, stop_after_spawn=True)
    window = rec["hang_window"]
    assert window is not None, rec
    assert window["token_delta"] == 0 and window["cpu_delta"] == 0 and window["output_bytes_delta"] == 0, rec
    assert window["seconds"] >= hang, rec
    assert "T" in rec["child_states_seen"], rec  # observed in the stopped state under /proc
    assert rec["status"] == "FAILED" and rec["classification"] == "HUNG", rec
    assert rec["status"] != "SUCCESS"
    return rec


def test_longrun_scripts_reused() -> dict[str, Any]:
    """tools/plugin/longrun.py delegates to scripts/longrun.sh|ps1 rather than a private runner."""
    present = {rel: (REPO / rel).is_file() for rel in LONGRUN_SCRIPTS}
    assert all(present.values()), present
    script = longrun_entry.longrun_script()
    assert script.resolve() in {(REPO / rel).resolve() for rel in LONGRUN_SCRIPTS}, script
    run = longrun_entry.run(
        [sys.executable, "-S", "-B", "-c", "print('reuse-ok')"],
        ident="imp0058-reuse",
        heartbeat_sec=1,
        hang_timeout_sec=0,
    )
    marker = next((line for line in run.stdout.splitlines() if line.startswith("SUCCESS:imp0058-reuse")), None)
    reused = run.returncode == 0 and marker is not None and "longrun[imp0058-reuse] starting" in run.stdout
    assert reused, {"rc": run.returncode, "stdout": run.stdout[-600:], "stderr": run.stderr[-600:]}
    return {
        "reused": reused,
        "scripts": list(LONGRUN_SCRIPTS),
        "script_used": str(script.relative_to(REPO)).replace("\\", "/"),
        "exit_code": run.returncode,
        "marker": marker,
    }


def test_mtime_not_consulted_in_classifier() -> dict[str, Any]:
    """No hang path in the engine or wrappers reads a file modification time."""
    patterns = [re.compile(p) for p in MTIME_PATTERNS]
    hits: list[dict[str, Any]] = []
    scanned: list[str] = []
    for rel in CLASSIFIER_FILES:
        path = REPO / rel
        assert path.is_file(), rel
        scanned.append(rel)
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for pat in patterns:
                if pat.search(line):
                    hits.append({"path": rel, "line": lineno, "pattern": pat.pattern, "text": line.strip()[:160]})
                    break
    assert "st_mtime" not in Path(hb_engine.__file__).read_text(encoding="utf-8")
    assert not hits, hits
    return {"hits": hits, "scanned": scanned, "patterns": list(MTIME_PATTERNS)}


def main() -> int:
    results = {
        "slow": test_token_advances_during_a_slow_op(),
        "silent": test_silence_is_not_hang(),
        "hung": test_hung_child_reports_failed_not_success(),
        "reuse": test_longrun_scripts_reused(),
        "mtime": test_mtime_not_consulted_in_classifier(),
    }
    for rec in results.values():
        rec.pop("stdout_tail", None)
    print(json.dumps(results, sort_keys=True, default=str))
    print("SUCCESS:IMP-0058 test_heartbeat token+cpu liveness; hung child FAILED; mtime unused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
