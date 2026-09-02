#!/usr/bin/env python3
"""Live kill/resume/corrupt experiments for CNF-0079."""
from __future__ import annotations

import json
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
import workflow as W  # noqa: E402

KILL_POINTS = ("ingest", "transform", "fuse")
RUNNER = HERE / "workflow.py"


def py_cmd() -> list[str]:
    return [sys.executable, "-B", str(RUNNER)]


def wait_for(path: Path, timeout: float = 60.0) -> None:
    """Block until path exists non-empty.

    The default budget is generous because the measurement host runs under
    chronic memory pressure: a child interpreter start can take well over
    the 8s this used to allow. The semantics under test (checkpoint
    durability across SIGKILL) do not depend on the wait budget.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.is_file() and path.stat().st_size > 0:
            return
        time.sleep(0.02)
    raise TimeoutError(f"timed out waiting for {path}")


def kill_then_resume(workdir: Path, kill_after: str) -> dict[str, Any]:
    """SIGKILL the child after a durable checkpoint at kill_after, then resume."""
    workdir.mkdir(parents=True, exist_ok=True)
    paused = workdir / "PAUSED"
    ckpt = workdir / "checkpoint.json"
    if paused.exists():
        paused.unlink()
    proc = subprocess.Popen(
        py_cmd() + ["run", "--workdir", str(workdir), "--pause-after", kill_after],
        cwd=str(HERE),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_for(paused)
        wait_for(ckpt)
        body = json.loads(ckpt.read_text(encoding="utf-8"))
        completed = body.get("completed_stages") or []
        if completed[-1:] != [kill_after]:
            raise RuntimeError(
                f"checkpoint at kill was {completed}, want ending {kill_after}"
            )
        snapshot = json.loads(json.dumps(body))
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    if paused.exists():
        paused.unlink()
    resumed = subprocess.run(
        py_cmd() + ["run", "--workdir", str(workdir), "--resume"],
        cwd=str(HERE),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if resumed.returncode != 0:
        raise RuntimeError(
            f"resume after kill-{kill_after} failed rc={resumed.returncode} "
            f"stderr={resumed.stderr[-1500:]}"
        )
    payload = json.loads(resumed.stdout)
    artifact_path = workdir / "artifact.json"
    effects = W.effect_counts(workdir / "effects.log")
    return {
        "kill_after": kill_after,
        "kill_signal": "SIGKILL",
        "child_return": proc.returncode,
        "checkpoint_at_kill": snapshot,
        "resume": payload,
        "artifact": json.loads(artifact_path.read_text(encoding="utf-8")),
        "artifact_sha256": W.sha256_bytes(artifact_path.read_bytes()),
        "skipped_on_resume": list(payload.get("skipped") or []),
        "executed_on_resume": list(payload.get("executed") or []),
        "effects": effects,
        "side_effect_replay": any(n > 1 for n in effects.values()),
    }


def uninterrupted(workdir: Path) -> dict[str, Any]:
    result = W.run_workflow(workdir, W.DEFAULT_INPUT)
    artifact_path = workdir / "artifact.json"
    return {
        "status": result["status"],
        "executed": result["executed"],
        "skipped": result["skipped"],
        "artifact": json.loads(artifact_path.read_text(encoding="utf-8")),
        "artifact_sha256": W.sha256_bytes(artifact_path.read_bytes()),
        "effects": result["effects"],
        "checkpoint": result["checkpoint"],
    }


def corrupt_checkpoint_refused(workdir: Path) -> dict[str, Any]:
    W.run_workflow(workdir, W.DEFAULT_INPUT, stop_after="transform")
    ckpt_path = workdir / "checkpoint.json"
    before = ckpt_path.read_bytes()
    doc = json.loads(before.decode("utf-8"))
    original = str(doc.get("integrity") or "aa")
    tampered = dict(doc)
    tampered["integrity"] = ("0" if original[:1] != "0" else "1") + original[1:]
    ckpt_path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")
    effects_before = W.effect_counts(workdir / "effects.log")
    stages_before = sorted(p.name for p in (workdir / "stages").glob("*.json"))
    refused = subprocess.run(
        py_cmd() + ["run", "--workdir", str(workdir), "--resume"],
        cwd=str(HERE),
        capture_output=True,
        text=True,
        timeout=120,
    )
    effects_after = W.effect_counts(workdir / "effects.log")
    stages_after = sorted(p.name for p in (workdir / "stages").glob("*.json"))
    stderr = (refused.stderr or "") + (refused.stdout or "")
    return {
        "exit_code": refused.returncode,
        "stderr_tail": stderr[-1500:],
        "refused": refused.returncode == 2 and "REFUSED:corrupt-checkpoint" in stderr,
        "effects_before": effects_before,
        "effects_after": effects_after,
        "stages_unchanged": stages_before == stages_after,
        "effects_unchanged": effects_before == effects_after,
        "tamper": "integrity-hex-flip",
        "checkpoint_bytes_before": len(before),
    }


def redo_completed_detected(workdir: Path) -> dict[str, Any]:
    W.run_workflow(workdir, W.DEFAULT_INPUT, stop_after="ingest")
    broken = W.run_workflow(
        workdir, W.DEFAULT_INPUT, resume=True, redo_completed=True
    )
    replay = any(n > 1 for n in broken["effects"].values())
    return {
        "fired": replay,
        "effects": broken["effects"],
        "executed_on_resume": broken["executed"],
        "skipped_on_resume": broken["skipped"],
    }


def field_diff(left: Any, right: Any, prefix: str = "") -> list[str]:
    if type(left) is not type(right):
        return [prefix or "$"]
    if isinstance(left, dict):
        keys = sorted(set(left) | set(right))
        out: list[str] = []
        for key in keys:
            path = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                out.append(path)
            else:
                out.extend(field_diff(left[key], right[key], path))
        return out
    if isinstance(left, list):
        if len(left) != len(right):
            return [prefix or "$"]
        out = []
        for i, (a, b) in enumerate(zip(left, right)):
            out.extend(field_diff(a, b, f"{prefix}[{i}]"))
        return out
    if left != right:
        return [prefix or "$"]
    return []


def run_suite() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cnf0079-") as tmp:
        root = Path(tmp)
        clean = uninterrupted(root / "clean")
        kills = []
        for stage in KILL_POINTS:
            row = kill_then_resume(root / f"kill-{stage}", stage)
            want_skip = list(W.STAGES[: W.STAGES.index(stage) + 1])
            want_run = list(W.STAGES[W.STAGES.index(stage) + 1 :])
            equivalent = row["artifact_sha256"] == clean["artifact_sha256"]
            diffs = field_diff(clean["artifact"], row["artifact"])
            replay = row["side_effect_replay"]
            skipped_ok = row["skipped_on_resume"] == want_skip
            executed_ok = row["executed_on_resume"] == want_run
            kills.append(
                {
                    "id": f"kill-after-{stage}",
                    "kill_after": stage,
                    "kill_signal": row["kill_signal"],
                    "child_return": row["child_return"],
                    "checkpoint_at_kill": row["checkpoint_at_kill"],
                    "skipped_on_resume": row["skipped_on_resume"],
                    "executed_on_resume": row["executed_on_resume"],
                    "expected_skipped": want_skip,
                    "expected_executed": want_run,
                    "skipped_ok": skipped_ok,
                    "executed_ok": executed_ok,
                    "left_sha256": clean["artifact_sha256"],
                    "right_sha256": row["artifact_sha256"],
                    "equivalent": equivalent,
                    "differing_fields": diffs,
                    "effects": row["effects"],
                    "side_effect_replay": replay,
                    "clean_effects": clean["effects"],
                    "pass": equivalent and skipped_ok and executed_ok and not replay,
                }
            )
        corrupt = corrupt_checkpoint_refused(root / "corrupt")
        detector = redo_completed_detected(root / "redo")
        return {
            "clean": {
                "artifact_sha256": clean["artifact_sha256"],
                "executed": clean["executed"],
                "effects": clean["effects"],
                "artifact": clean["artifact"],
            },
            "kills": kills,
            "corrupt": corrupt,
            "redo_detector": detector,
        }


if __name__ == "__main__":
    doc = run_suite()
    print(
        json.dumps(
            {
                k: (
                    v
                    if k != "kills"
                    else [
                        {
                            kk: vv
                            for kk, vv in row.items()
                            if kk != "checkpoint_at_kill"
                        }
                        for row in v
                    ]
                )
                for k, v in doc.items()
            },
            indent=2,
            sort_keys=True,
        )
    )
