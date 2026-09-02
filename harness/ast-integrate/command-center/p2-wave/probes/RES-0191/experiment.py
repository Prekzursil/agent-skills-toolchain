#!/usr/bin/env python3
"""Kill / resume / corrupt / naive-mutant experiment for RES-0191."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "engine.py"
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

PY = [sys.executable, "-B", str(ENGINE)]


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        PY + args,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )


def _load(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))


def control_run() -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="res0191-control-"))
    try:
        proc = _run(["run", "--dir", str(tmp), "--run-id", "control"], tmp)
        if proc.returncode != 0:
            raise RuntimeError(
                f"control failed rc={proc.returncode} {proc.stderr} {proc.stdout}"
            )
        doc = E.load_checkpoint(tmp)
        return {
            "claims": E.claim_set(doc),
            "status": E.status_map(doc),
            "pay": E.backend_ledger(doc),
            "persist_count": doc["persist_count"],
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def kill_and_resume(die_after: int = E.DIE_AFTER_DEFAULT) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="res0191-kill-"))
    try:
        killed = _run(
            [
                "run",
                "--dir",
                str(tmp),
                "--run-id",
                "killed",
                "--die-after",
                str(die_after),
                "--die-mode",
                "sigkill",
            ],
            tmp,
        )
        # SIGKILL -> -9; _exit(99) fallback; some sandboxes report 137.
        if killed.returncode not in {-9, 9, 99, 137}:
            raise RuntimeError(
                f"expected mid-run death, rc={killed.returncode} "
                f"err={killed.stderr!r} out={killed.stdout!r}"
            )
        mid = E.load_checkpoint(tmp)
        mid_status = E.status_map(mid)
        mid_pay = E.backend_ledger(mid)
        if mid_status.get("Q1") != "completed":
            raise RuntimeError(f"kill point missed Q1 completed: {mid_status}")
        if mid_status.get("Q2") != "partial":
            raise RuntimeError(f"kill point missed Q2 partial: {mid_status}")
        if mid_status.get("Q3") != "failed":
            raise RuntimeError(f"kill point missed Q3 failed: {mid_status}")
        if mid_status.get("Q4") != "partial":
            raise RuntimeError(f"kill point missed Q4 partial: {mid_status}")

        resumed = _run(["resume", "--dir", str(tmp), "--run-id", "killed"], tmp)
        if resumed.returncode != 0:
            raise RuntimeError(
                f"resume failed rc={resumed.returncode} {resumed.stderr} {resumed.stdout}"
            )
        final = E.load_checkpoint(tmp)
        return {
            "kill_rc": killed.returncode,
            "mid_status": mid_status,
            "mid_claims": E.claim_set(mid),
            "mid_pay": mid_pay,
            "final_status": E.status_map(final),
            "final_claims": E.claim_set(final),
            "final_pay": E.backend_ledger(final),
            "q1_not_repaid": mid_pay["Q1"] == E.backend_ledger(final)["Q1"],
            "q2_continued": E.backend_ledger(final)["Q2"] > mid_pay["Q2"],
            "q3_retried": E.backend_ledger(final)["Q3"] > mid_pay["Q3"],
            "q4_continued": E.backend_ledger(final)["Q4"] > mid_pay["Q4"],
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def corrupt_byte_flip_refuses() -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="res0191-flip-"))
    try:
        proc = _run(["run", "--dir", str(tmp), "--run-id", "flip"], tmp)
        if proc.returncode != 0:
            raise RuntimeError(f"setup run failed {proc.returncode} {proc.stderr}")
        path = tmp / "checkpoint.json"
        raw = path.read_bytes()
        path.write_bytes(E.flip_byte(raw))
        refused = _run(["resume", "--dir", str(tmp)], tmp)
        text = (refused.stdout or "") + (refused.stderr or "")
        return {
            "rc": refused.returncode,
            "text": text.strip(),
            "loud": refused.returncode == 2
            and (
                "REFUSE:checkpoint-integrity" in text
                or "REFUSE:checkpoint-unreadable" in text
            ),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def corrupt_inconsistent_completed_refuses() -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="res0191-incon-"))
    kill_dir = Path(tempfile.mkdtemp(prefix="res0191-incon-src-"))
    try:
        killed = _run(
            [
                "run",
                "--dir",
                str(kill_dir),
                "--die-after",
                str(E.DIE_AFTER_DEFAULT),
                "--die-mode",
                "sigkill",
            ],
            kill_dir,
        )
        if killed.returncode not in {-9, 9, 99, 137}:
            raise RuntimeError(f"kill setup rc={killed.returncode}")
        mid = E.load_checkpoint(kill_dir)
        forged = E.forge_inconsistent_completed(mid)
        (tmp / "checkpoint.json").write_text(
            json.dumps(forged, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        refused = _run(["resume", "--dir", str(tmp)], tmp)
        text = (refused.stdout or "") + (refused.stderr or "")
        return {
            "rc": refused.returncode,
            "text": text.strip(),
            "loud": refused.returncode == 2
            and "REFUSE:checkpoint-inconsistent-completed" in text,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(kill_dir, ignore_errors=True)


def naive_mutant_drops_claims() -> dict[str, Any]:
    src_dir = Path(tempfile.mkdtemp(prefix="res0191-naive-src-"))
    dst_dir = Path(tempfile.mkdtemp(prefix="res0191-naive-dst-"))
    try:
        killed = _run(
            [
                "run",
                "--dir",
                str(src_dir),
                "--die-after",
                str(E.DIE_AFTER_DEFAULT),
                "--die-mode",
                "sigkill",
            ],
            src_dir,
        )
        if killed.returncode not in {-9, 9, 99, 137}:
            raise RuntimeError(f"kill setup rc={killed.returncode}")
        mid = E.load_checkpoint(src_dir)
        naive = E.naive_skip_nonzero(dst_dir, mid)
        dropped = sorted(set(E.expected_full_claims()) - set(E.claim_set(naive)))
        return {
            "naive_claims": E.claim_set(naive),
            "dropped": dropped,
            "silent_skip": bool(dropped),
        }
    finally:
        shutil.rmtree(src_dir, ignore_errors=True)
        shutil.rmtree(dst_dir, ignore_errors=True)


def run_experiment() -> dict[str, Any]:
    control = control_run()
    kr = kill_and_resume()
    flip = corrupt_byte_flip_refuses()
    incon = corrupt_inconsistent_completed_refuses()
    naive = naive_mutant_drops_claims()
    match = control["claims"] == kr["final_claims"] == E.expected_full_claims()
    all_completed = set(kr["final_status"].values()) == {"completed"}
    ok = (
        match
        and all_completed
        and kr["q1_not_repaid"]
        and kr["q2_continued"]
        and kr["q3_retried"]
        and kr["q4_continued"]
        and flip["loud"]
        and incon["loud"]
        and naive["silent_skip"]
    )
    return {
        "ok": ok,
        "control": control,
        "kill_resume": kr,
        "byte_flip": {"rc": flip["rc"], "loud": flip["loud"], "text": flip["text"][-400:]},
        "inconsistent_completed": {
            "rc": incon["rc"],
            "loud": incon["loud"],
            "text": incon["text"][-400:],
        },
        "naive_mutant": naive,
        "expected_claims": E.expected_full_claims(),
        "claim_set_match": match,
    }


def main() -> int:
    report = run_experiment()
    print(json.dumps({k: report[k] for k in ("ok", "claim_set_match")}, sort_keys=True))
    if not report["ok"]:
        print(json.dumps(report, indent=2, sort_keys=True)[:4000])
        print("FAILED:RES-0191-experiment")
        return 1
    print("SUCCESS:RES-0191-experiment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
