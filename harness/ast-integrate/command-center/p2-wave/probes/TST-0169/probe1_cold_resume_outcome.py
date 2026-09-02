#!/usr/bin/env python3
"""Probe 1 / signal (a): live cold-resume outcome from a clean shell.

Simulates reboot by wiping the session temp dir, starting a new process with a
clean environment (no previous-session env, no inherited cwd, fresh TMPDIR),
and resuming only via --durable-root. Warm resume in the same session is the
both-states control. Planting a temp-dir sidecar is the detector control.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from cold_resume import STEPS, persist_durable_checkpoint, resume_from_durable  # noqa: E402
from handled_ledger import is_under_temp  # noqa: E402

ENGINE = HERE / "cold_resume.py"
LEDGER_CLI = HERE / "ledger_cli.mjs"
CATALOG_LEDGER = REPO / "tools" / "lib" / "handled-ledger.mjs"
OUT = HERE / "probe1-cold-resume.raw.json"
RUNTIME = HERE / "runtime" / "probe1"


def _clean_env(tmp_dir: Path, home: Path) -> dict[str, str]:
    path = os.environ.get("PATH") or "/usr/bin:/bin"
    return {
        "PATH": path,
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TMPDIR": str(tmp_dir),
        "TEMP": str(tmp_dir),
        "TMP": str(tmp_dir),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PREVIOUS_RUN_PID": str(os.getpid()),
        "SESSION_CHECKPOINT": "/nonexistent/previous-session-checkpoint",
        "HANDLED_LEDGER_PATH": "/nonexistent/previous-session-ledger",
    }


def _node_bin() -> str | None:
    return shutil.which("node")


def _run_mjs(
    action: str,
    state_dir: Path,
    *,
    tmp: Path,
    home: Path,
    cwd: Path,
    run_id: str,
) -> subprocess.CompletedProcess[str]:
    node = _node_bin()
    if not node:
        raise FileNotFoundError("node binary missing")
    cmd = [
        node,
        str(LEDGER_CLI),
        action,
        "--ledger",
        str(CATALOG_LEDGER),
        "--state-dir",
        str(state_dir),
        "--key",
        "tst-0169",
        "--id",
        run_id,
    ]
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=_clean_env(tmp, home),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _run(action: str, durable: Path, *, tmp: Path, home: Path, cwd: Path, extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        "-B",
        str(ENGINE),
        action,
        "--durable-root",
        str(durable),
    ]
    if extra:
        cmd.extend(extra)
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=_clean_env(tmp, home),
        capture_output=True,
        text=True,
        timeout=30,
    )


def main() -> int:
    if RUNTIME.exists():
        shutil.rmtree(RUNTIME)
    durable = RUNTIME / "durable"
    session_tmp = RUNTIME / "session_tmp"
    post_tmp = RUNTIME / "post_reboot_tmp"
    home = RUNTIME / "clean_home"
    cwd = RUNTIME / "clean_cwd"
    for path in (durable, session_tmp, post_tmp, home, cwd):
        path.mkdir(parents=True, exist_ok=True)

    persist_durable_checkpoint(durable, "run-warm", "warm-payload")
    if is_under_temp(durable / "checkpoint.json"):
        print("FAILED:TST-0169-probe1 durable store landed under temp")
        return 1

    os.environ["PREVIOUS_RUN_PID"] = str(os.getpid())
    os.environ["SESSION_CHECKPOINT"] = "/nonexistent/in-session"
    warm = resume_from_durable(durable)
    warm_ok = warm.get("completed") == list(STEPS) and warm.get("resumed") is True
    if not warm_ok:
        print("FAILED:TST-0169-probe1 warm resume did not finish", warm)
        return 1

    persist_durable_checkpoint(durable, "run-cold", "cold-payload")
    (session_tmp / "stale-pid").write_text(str(os.getpid()), encoding="utf-8")
    shutil.rmtree(session_tmp)
    session_tmp.mkdir()
    cold = _run("resume", durable, tmp=post_tmp, home=home, cwd=cwd)
    cold_ok = cold.returncode == 0 and "SUCCESS:cold-resume action=resume" in (cold.stdout or "")
    if not cold_ok:
        print("FAILED:TST-0169-probe1 cold resume")
        print(cold.stdout)
        print(cold.stderr)
        return 1

    mutant_root = RUNTIME / "mutant_durable"
    mutant_root.mkdir(parents=True, exist_ok=True)
    plant = _run(
        "mutant-persist",
        mutant_root,
        tmp=session_tmp,
        home=home,
        cwd=cwd,
        extra=["--run-id", "run-mutant", "--payload", "mutant"],
    )
    if plant.returncode != 0:
        print("FAILED:TST-0169-probe1 mutant persist")
        print(plant.stdout)
        print(plant.stderr)
        return 1
    shutil.rmtree(session_tmp)
    session_tmp.mkdir()
    planted_fail = _run("mutant-resume", mutant_root, tmp=post_tmp, home=home, cwd=cwd)
    detector_fired = planted_fail.returncode != 0 and "TEMP-DEPENDENCY" in (
        (planted_fail.stdout or "") + (planted_fail.stderr or "")
    )
    if not detector_fired:
        print("FAILED:TST-0169-probe1 detector control did not fire")
        print(planted_fail.stdout)
        print(planted_fail.stderr)
        return 1

    still_good = _run("resume", durable, tmp=post_tmp, home=home, cwd=cwd)
    if still_good.returncode != 0:
        print("FAILED:TST-0169-probe1 good engine failed after detector control")
        return 1

    mjs_arm: dict = {
        "catalog_input": "tools/lib/handled-ledger.mjs",
        "present": CATALOG_LEDGER.is_file(),
        "node": _node_bin(),
        "cold_resume_pass": None,
        "detector_fired": None,
    }
    if CATALOG_LEDGER.is_file():
        if not _node_bin():
            print("FAILED:TST-0169-probe1 catalog ledger present but node missing")
            return 1
        mjs_state = RUNTIME / "mjs_durable"
        mjs_state.mkdir(parents=True, exist_ok=True)
        mjs_persist = _run_mjs(
            "persist", mjs_state, tmp=session_tmp, home=home, cwd=cwd, run_id="run-mjs"
        )
        if mjs_persist.returncode != 0:
            print("FAILED:TST-0169-probe1 mjs persist")
            print(mjs_persist.stdout)
            print(mjs_persist.stderr)
            return 1
        shutil.rmtree(session_tmp)
        session_tmp.mkdir()
        mjs_cold = _run_mjs(
            "resume", mjs_state, tmp=post_tmp, home=home, cwd=cwd, run_id="run-mjs"
        )
        mjs_ok = mjs_cold.returncode == 0 and "SUCCESS:mjs-cold-resume action=resume" in (
            mjs_cold.stdout or ""
        )
        if not mjs_ok:
            print("FAILED:TST-0169-probe1 mjs cold resume")
            print(mjs_cold.stdout)
            print(mjs_cold.stderr)
            return 1
        mjs_plant = _run_mjs(
            "mutant-persist",
            mjs_state,
            tmp=session_tmp,
            home=home,
            cwd=cwd,
            run_id="run-mjs-mutant",
        )
        if mjs_plant.returncode != 0:
            print("FAILED:TST-0169-probe1 mjs mutant persist")
            print(mjs_plant.stdout)
            print(mjs_plant.stderr)
            return 1
        shutil.rmtree(session_tmp)
        session_tmp.mkdir()
        mjs_fail = _run_mjs(
            "mutant-resume",
            mjs_state,
            tmp=post_tmp,
            home=home,
            cwd=cwd,
            run_id="run-mjs-mutant",
        )
        mjs_detector = mjs_fail.returncode != 0 and "TEMP-DEPENDENCY" in (
            (mjs_fail.stdout or "") + (mjs_fail.stderr or "")
        )
        if not mjs_detector:
            print("FAILED:TST-0169-probe1 mjs detector control did not fire")
            print(mjs_fail.stdout)
            print(mjs_fail.stderr)
            return 1
        mjs_arm["cold_resume_pass"] = True
        mjs_arm["detector_fired"] = True
        mjs_arm["cold_stdout_tail"] = (mjs_cold.stdout or "")[-400:]

    doc = {
        "probe": "probe1-cold-resume-outcome",
        "unit_id": "TST-0169",
        "warm_resume_pass": True,
        "cold_resume_pass": True,
        "cold_returncode": cold.returncode,
        "detector_temp_dependency_fired": True,
        "detector_returncode": planted_fail.returncode,
        "durable_not_under_temp": True,
        "catalog_ledger": mjs_arm,
        "clean_shell": {
            "new_process": True,
            "fresh_tmpdir": str(post_tmp.relative_to(REPO)),
            "session_tmp_wiped": True,
            "session_env_traps_ignored": [
                "PREVIOUS_RUN_PID",
                "SESSION_CHECKPOINT",
                "HANDLED_LEDGER_PATH",
            ],
        },
        "cold_stdout_tail": (cold.stdout or "")[-800:],
        "detector_stdout_tail": ((planted_fail.stdout or "") + (planted_fail.stderr or ""))[-800:],
        "pass": True,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "warm_ok=True cold_ok=True detector_fired=True "
        f"mjs_ok={mjs_arm.get('cold_resume_pass')} "
        f"durable={durable.relative_to(REPO).as_posix()}"
    )
    print("SUCCESS:TST-0169-probe1 cold-resume outcome")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
