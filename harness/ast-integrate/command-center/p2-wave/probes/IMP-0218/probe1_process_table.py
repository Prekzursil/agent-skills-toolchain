#!/usr/bin/env python3
"""IMP-0218 probe1: process-table measurement after a checkpoint.

Signal: process count matching the executor marker returns to the pre-checkpoint
baseline after the executor returns. A busy-wait control stays resident until
killed (detector fires on bad, silent on good).
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import proc_count as PC  # noqa: E402

EXECUTOR = REPO / "tools/agentspec/agentspec/human_checkpoint.py"
BUSYWAIT = HERE / "busywait_control.py"
OUT = HERE / "probe1-process-table.raw.json"
WAIT_APIS = frozenset({"sleep", "wait", "input", "fork", "forkpty", "pause"})


def _busywait_surface(source: str) -> list[str]:
    tree = ast.parse(source)
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value is True:
            hits.append(f"while_true:line{node.lineno}")
        if isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name in WAIT_APIS:
                hits.append(f"call:{name}:line{node.lineno}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {"threading", "multiprocessing"}:
                    hits.append(f"import:{alias.name}:line{node.lineno}")
        if isinstance(node, ast.ImportFrom) and node.module in {"threading", "multiprocessing"}:
            hits.append(f"import:{node.module}:line{node.lineno}")
    return hits


def _run(cmd: list[str], *, timeout: float, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        merged.update(env)
    return subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=merged,
    )


def _kill(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)


def main() -> int:
    if not EXECUTOR.is_file():
        print("FAILED:IMP-0218-probe1 executor missing", EXECUTOR)
        return 1
    source = EXECUTOR.read_text(encoding="utf-8")
    surface = _busywait_surface(source)
    if surface:
        print("FAILED:IMP-0218-probe1 executor busy-wait surface", surface)
        return 1

    marker_good = f"IMP-0218-NOWAIT-{uuid.uuid4().hex}"
    marker_bad = f"IMP-0218-BUSYWAIT-{uuid.uuid4().hex}"
    me = {os.getpid()}
    baseline_good = PC.count_cmdline(marker_good, exclude_pids=me)
    baseline_bad = PC.count_cmdline(marker_bad, exclude_pids=me)

    with tempfile.TemporaryDirectory(prefix="imp-0218-p1-") as tmp:
        ws = Path(tmp)
        cmd = [
            sys.executable,
            "-B",
            str(EXECUTOR),
            "pause",
            "--workspace",
            str(ws),
            "--checkpoint-id",
            "cp-owner-gate",
            "--prompt-ref",
            "owner.ratify-architecture",
            "--question",
            "Ratify architecture A2, or override it?",
            "--recommendation",
            "Ratify A2; downstream IMP units are staged against it.",
            "--tradeoff",
            "Override is reversible but freezes every unit that depends on ratification.",
            "--default",
            "ratify",
            "--allowed",
            "ratify",
            "override",
            "--completed",
            "IMP-0131=" + ("a" * 64),
            "--marker",
            marker_good,
        ]
        try:
            ran = _run(cmd, timeout=8)
        except subprocess.TimeoutExpired:
            print("FAILED:IMP-0218-probe1 executor still resident (timeout)")
            return 1
        after_good = PC.cmdline_pids(marker_good, exclude_pids=me)
        if ran.returncode != 0:
            print("FAILED:IMP-0218-probe1 executor exit", ran.returncode, ran.stdout, ran.stderr)
            return 1
        if after_good:
            print("FAILED:IMP-0218-probe1 resident after checkpoint", after_good)
            return 1
        envelope = json.loads(ran.stdout)
        if envelope.get("resident_waiter") is not False or envelope.get("hang") is not False:
            print("FAILED:IMP-0218-probe1 envelope claims a waiter", envelope)
            return 1
        pause_path = Path(envelope["pause_record_path"])
        if not pause_path.is_file():
            print("FAILED:IMP-0218-probe1 pause record missing")
            return 1

        busy = subprocess.Popen(
            [sys.executable, "-B", str(BUSYWAIT), "--marker", marker_bad],
            cwd=str(REPO),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.time() + 4
            during_bad: list[int] = []
            while time.time() < deadline:
                during_bad = PC.cmdline_pids(marker_bad, exclude_pids=me)
                if during_bad and busy.poll() is None:
                    break
                time.sleep(0.05)
            fired_on_bad = bool(during_bad) and busy.poll() is None
        finally:
            _kill(busy)
        after_bad = PC.cmdline_pids(marker_bad, exclude_pids=me)
        silent_after_kill = not after_bad
        if not fired_on_bad or not silent_after_kill:
            print(
                "FAILED:IMP-0218-probe1 both-states process-table",
                f"fired_on_bad={fired_on_bad} silent_after_kill={silent_after_kill}",
                during_bad,
                after_bad,
            )
            return 1

        doc = {
            "probe": "probe1-process-table",
            "unit_id": "IMP-0218",
            "pass": True,
            "executor_busywait_surface": surface,
            "baseline_good": baseline_good,
            "after_checkpoint_pids": after_good,
            "after_checkpoint_count": len(after_good),
            "executor_exit_code": ran.returncode,
            "pause_record_exists": pause_path.is_file(),
            "envelope_status": envelope.get("status"),
            "resident_waiter": envelope.get("resident_waiter"),
            "hang": envelope.get("hang"),
            "busywait_control": {
                "fired_on_bad": fired_on_bad,
                "silent_after_kill": silent_after_kill,
                "during_count": len(during_bad),
                "after_kill_count": len(after_bad),
                "baseline_bad": baseline_bad,
            },
        }
        OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            f"baseline={baseline_good} after_checkpoint={len(after_good)} "
            f"fired_on_bad={fired_on_bad} silent_after_kill={silent_after_kill} "
            f"busywait_surface={surface}"
        )
        print("SUCCESS:IMP-0218-probe1 no resident process after checkpoint")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
