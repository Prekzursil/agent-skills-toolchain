"""Live SIGKILL-then-resume scenarios for TST-0096.

Each helper builds a disposable workspace, spawns runner.py as a child, and
returns measured dispatch/hash facts. Probes and the receipt emitter share
this so the artifact cannot claim a run the probes cannot reproduce.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import plan as P  # noqa: E402
import runner as R  # noqa: E402

RUNNER = HERE / "runner.py"


def spawn(
    root: Path,
    *,
    resume: bool = False,
    kill_at: str | None = None,
    broken: str | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    cmd = [sys.executable, "-B", str(RUNNER), "--root", str(root)]
    if resume:
        cmd.append("--resume")
    if kill_at:
        cmd.extend(["--kill-at", kill_at])
    if broken:
        cmd.extend(["--broken", broken])
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(HERE),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "cmd": cmd,
    }


def _snapshot(root: Path, units: list[dict[str, Any]]) -> dict[str, Any]:
    cp = R.load_checkpoint(root) or {}
    index = {u["id"]: u for u in units}
    complete: list[str] = []
    oracle_rows: list[dict[str, Any]] = []
    for rec in cp.get("completed") or []:
        uid = rec.get("id")
        if uid not in index:
            continue
        v = P.unit_oracle(root, index[uid], rec)
        oracle_rows.append({"id": uid, **v})
        if v["pass"]:
            complete.append(str(uid))
    in_prog = cp.get("in_progress") or {}
    in_id = in_prog.get("id") if isinstance(in_prog, dict) else None
    if in_id and in_id in index:
        v = P.unit_oracle(root, index[in_id], None)
        oracle_rows.append({"id": in_id, "in_progress": True, **v})
    incomplete = [u["id"] for u in units if u["id"] not in complete]
    return {
        "completed_ids": complete,
        "incomplete_ids": incomplete,
        "in_progress": in_id,
        "dispatches": dict(cp.get("dispatches") or {}),
        "last_checkpoint": cp.get("last_checkpoint"),
        "artifact_set_hash": P.artifact_set_hash(root, units),
        "oracle": oracle_rows,
        "checkpoint_present": R.checkpoint_path(root).is_file(),
    }


def _reexecuted(before: dict[str, int], after: dict[str, int]) -> list[str]:
    keys = sorted(set(before) | set(after), key=lambda k: (len(k), k))
    return [k for k in keys if int(after.get(k, 0)) > int(before.get(k, 0))]


def _prepare_root(root: Path) -> list[dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=True)
    P.write_plan(root)
    return P.PLAN


def run_clean(root: Path) -> dict[str, Any]:
    units = _prepare_root(root)
    spawned = spawn(root)
    snap = _snapshot(root, units)
    ok = (
        spawned["returncode"] == 0
        and "SUCCESS:runner-complete" in spawned["stdout"]
        and snap["completed_ids"] == [u["id"] for u in units]
        and snap["incomplete_ids"] == []
        and all(int((snap["dispatches"] or {}).get(u["id"], 0)) == 1 for u in units)
    )
    return {
        "pass": ok,
        "stage": "clean",
        "spawn": {"returncode": spawned["returncode"], "stdout": spawned["stdout"][-800:]},
        **snap,
    }


def run_kill_resume(
    root: Path,
    kill_at: str,
    *,
    broken: str | None = None,
) -> dict[str, Any]:
    units = _prepare_root(root)
    killed = spawn(root, kill_at=kill_at)
    after_kill = _snapshot(root, units)
    if killed["returncode"] == 0:
        return {
            "pass": False,
            "reason": "kill-did-not-fire",
            "kill_at": kill_at,
            "kill_rc": killed["returncode"],
            "after_kill": after_kill,
            "broken": broken,
        }

    expected_done = P.expected_complete_ids(kill_at)
    expected_open = P.expected_incomplete_ids(kill_at)
    kill_ok = after_kill["completed_ids"] == expected_done

    mid_partial_ok = True
    if kill_at.startswith("mid:"):
        uid = kill_at.split(":", 1)[1]
        unit = next(u for u in units if u["id"] == uid)
        v = P.unit_oracle(root, unit, None)
        mid_partial_ok = v["pass"] is False and v["reason"] in {
            "unparseable",
            "sentinel-absent",
            "absent",
            "not-object",
        }

    resumed = spawn(root, resume=True, broken=broken)
    after_resume = _snapshot(root, units)
    reexec = _reexecuted(after_kill["dispatches"], after_resume["dispatches"])
    only_incomplete = set(reexec) == set(expected_open) and not (
        set(reexec) & set(expected_done)
    )
    no_complete_redispatch = not (set(reexec) & set(expected_done))

    honest = broken is None
    resume_ok = resumed["returncode"] == 0 and "SUCCESS:runner-complete" in resumed["stdout"]
    all_complete = after_resume["completed_ids"] == [u["id"] for u in units]

    result = {
        "kill_at": kill_at,
        "broken": broken,
        "kill_rc": killed["returncode"],
        "kill_stdout_tail": (killed["stdout"] or "")[-400:],
        "resume_rc": resumed["returncode"],
        "resume_stdout_tail": (resumed["stdout"] or "")[-400:],
        "after_kill": after_kill,
        "after_resume": after_resume,
        "reexecuted": reexec,
        "expected_complete": expected_done,
        "expected_incomplete": expected_open,
        "only_incomplete": only_incomplete,
        "no_complete_redispatch": no_complete_redispatch,
        "mid_partial_rejected": mid_partial_ok,
        "kill_state_matches": kill_ok,
        "resume_ok": resume_ok,
        "all_complete": all_complete,
        "typed_classification": (
            "partial-artifact" if kill_at.startswith("mid:") else "severed-stream"
        ),
    }
    if honest:
        result["pass"] = bool(
            killed["returncode"] != 0
            and kill_ok
            and mid_partial_ok
            and resume_ok
            and all_complete
            and only_incomplete
        )
        if not result["pass"]:
            result["reason"] = "honest-kill-resume-failed"
    else:
        # Detector inputs: caller asserts the planted bug is visible.
        result["pass"] = True
        result["reason"] = "control-raw"
    return result


def compare_to_clean(clean_hash: str, case: dict[str, Any]) -> dict[str, Any]:
    got = (case.get("after_resume") or {}).get("artifact_set_hash")
    equal = bool(got and got == clean_hash)
    return {
        "clean_hash": clean_hash,
        "resumed_hash": got,
        "equal": equal,
    }


def run_honest_matrix(base: Path) -> dict[str, Any]:
    clean = run_clean(base / "clean")
    cases = []
    all_ok = bool(clean.get("pass"))
    for cp in P.CHECKPOINTS:
        slug = cp.replace(":", "-")
        case = run_kill_resume(base / slug, cp)
        cmp_ = compare_to_clean(clean.get("artifact_set_hash") or "", case)
        case["hash_comparison"] = cmp_
        case["pass"] = bool(case.get("pass") and cmp_["equal"])
        if not case["pass"]:
            all_ok = False
        cases.append(case)
    four = len(cases) >= 4 and all(c.get("pass") for c in cases)
    only = all(c.get("only_incomplete") for c in cases)
    hashes = all((c.get("hash_comparison") or {}).get("equal") for c in cases)
    return {
        "pass": bool(all_ok and four and only and hashes),
        "clean": {
            "pass": clean.get("pass"),
            "artifact_set_hash": clean.get("artifact_set_hash"),
            "dispatches": clean.get("dispatches"),
            "completed_ids": clean.get("completed_ids"),
        },
        "cases": cases,
        "checkpoint_count": len(cases),
        "four_checkpoints": four,
        "all_only_incomplete": only,
        "all_hashes_equal": hashes,
    }


def run_negative_controls(base: Path, clean_hash: str) -> dict[str, Any]:
    """Planted-broken resume modes must be visible to the predicates.

    redispatch-complete: hash may still match (deterministic artifacts) but
    a completed unit is re-dispatched.
    skip-incomplete: mid-unit crash is treated as done; hash diverges and the
    incomplete unit is missing from re-executed.
    """
    red = run_kill_resume(
        base / "ctrl-redispatch", "after:u1", broken=R.BROKEN_REDISPATCH
    )
    red_cmp = compare_to_clean(clean_hash, red)
    red_fires = (not red["no_complete_redispatch"]) or (
        "u1" in (red.get("reexecuted") or [])
    )

    skip = run_kill_resume(base / "ctrl-skip", "mid:u2", broken=R.BROKEN_SKIP)
    skip_cmp = compare_to_clean(clean_hash, skip)
    skip_fires = (not skip["only_incomplete"]) or (not skip_cmp["equal"])

    honest = run_kill_resume(base / "ctrl-honest", "mid:u2")
    honest_cmp = compare_to_clean(clean_hash, honest)
    silent = bool(
        honest.get("only_incomplete")
        and honest_cmp["equal"]
        and honest.get("pass")
    )

    return {
        "pass": bool(red_fires and skip_fires and silent),
        "redispatch_complete": {
            "fired": red_fires,
            "reexecuted": red.get("reexecuted"),
            "no_complete_redispatch": red.get("no_complete_redispatch"),
            "hash_equal": red_cmp["equal"],
            "hash_comparison": red_cmp,
        },
        "skip_incomplete": {
            "fired": skip_fires,
            "reexecuted": skip.get("reexecuted"),
            "only_incomplete": skip.get("only_incomplete"),
            "hash_equal": skip_cmp["equal"],
            "hash_comparison": skip_cmp,
            "after_resume_completed": (skip.get("after_resume") or {}).get(
                "completed_ids"
            ),
        },
        "honest_mid_u2": {
            "silent_on_good": silent,
            "only_incomplete": honest.get("only_incomplete"),
            "hash_equal": honest_cmp["equal"],
            "reexecuted": honest.get("reexecuted"),
            "pass": honest.get("pass"),
        },
    }
