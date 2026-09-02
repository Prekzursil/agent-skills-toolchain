#!/usr/bin/env python3
"""Probe 2: A16 partition canary on the replacement, plus crash-path recovery.

Independent of probe 1's summary helpers: ballot counts are re-derived from
the raw ballot list, and the canary search is a string count over the
delivered context. Crash is a real SIGKILL of a child, then resume from
the checkpoint written before the kill.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from council.integrity.partition import (  # noqa: E402
    A16_ALLOWED_CANARY,
    A16_CANARY,
    ROLE_PARTITION,
    delivered_context,
    partition_ids_in_context,
    scan_token,
)
from council.participants.replace import replace_occupant  # noqa: E402
from council.simulate import (  # noqa: E402
    default_personas,
    initial_state,
    run_round,
)

SIM = REPO / "tools/council/simulate.py"
TIMEOUT = 20


def _fail(msg: str, extra=None) -> int:
    print(f"FAILED:TST-0278-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, sort_keys=True, default=str)[:4000])
    return 1


def _replacement() -> dict:
    p = default_personas()["persona-critic-replacement"]
    return {
        "persona_id": "persona-critic-replacement",
        "role": "critic",
        "script": p["script"],
    }


def recount(ballots: list, occupant_id: str, rounds: list[int] | None = None) -> int:
    n = 0
    for b in ballots:
        if b.get("occupant_id") != occupant_id:
            continue
        if rounds is not None and b.get("round") not in rounds:
            continue
        n += 1
    return n


def partition_and_poison_trap() -> dict | str:
    st = initial_state()
    run_round(st)
    departed = st["seats"]["seat-critic"]["active_occupant_id"]
    # Poison the departed occupant's cached prompt with the withheld canary.
    for occ in st["occupants"]:
        if occ["occupant_id"] == departed:
            occ["delivered_context"] = f"LEAKED CACHE {A16_CANARY}"
            occ["last_delivered_context"] = occ["delivered_context"]
    st["round"] = 2
    st = replace_occupant(st, "seat-critic", _replacement(), reason="inactivity")
    repl = st["seats"]["seat-critic"]["active_occupant_id"]
    ctx = delivered_context(st, repl)
    chair_id = st["seats"]["seat-chair"]["active_occupant_id"]
    chair_ctx = delivered_context(st, chair_id)
    return {
        "replacement_id": repl,
        "departed_id": departed,
        "replacement_context": ctx,
        "a16_hits_replacement": scan_token(ctx, A16_CANARY),
        "allowed_hits_replacement": scan_token(ctx, A16_ALLOWED_CANARY),
        "a16_hits_chair": scan_token(chair_ctx, A16_CANARY),
        "partition_ids": partition_ids_in_context(ctx),
        "mandate": list(ROLE_PARTITION["critic"]),
        "ballots_unattended": recount(st["ballots"], repl, [1]),
        "poisoned_departed_cache_has_canary": A16_CANARY
        in next(o["delivered_context"] for o in st["occupants"] if o["occupant_id"] == departed),
    }


def crash_kill_and_resume() -> dict | str:
    with tempfile.TemporaryDirectory(prefix="tst0278-crash-") as tmp:
        ckpt = str(Path(tmp) / "council.json")
        child = subprocess.run(
            [
                sys.executable,
                "-B",
                str(SIM),
                "--scenario",
                "crash-child",
                "--checkpoint",
                ckpt,
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        # SIGKILL typically yields returncode < 0 (POSIX) or 137.
        if child.returncode == 0:
            return f"crash-child exited 0 (did not die): {child.stdout[-500:]}"
        if not Path(ckpt).is_file():
            return f"checkpoint missing after kill rc={child.returncode} err={child.stderr[-500:]}"
        ckpt_doc = json.loads(Path(ckpt).read_text(encoding="utf-8"))
        if ckpt_doc.get("status") != "crashed":
            return f"checkpoint status={ckpt_doc.get('status')!r} not crashed"
        resume = subprocess.run(
            [
                sys.executable,
                "-B",
                str(SIM),
                "--scenario",
                "crash-resume",
                "--checkpoint",
                ckpt,
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        if resume.returncode != 0:
            return (
                f"crash-resume rc={resume.returncode} "
                f"stdout={resume.stdout[-800:]} stderr={resume.stderr[-800:]}"
            )
        final = json.loads(Path(ckpt).read_text(encoding="utf-8"))
        if final.get("status") != "complete":
            return f"resume status={final.get('status')!r}"
        # Independent recount: replacement occupant has 0 ballots in round 1.
        repl = final["seats"]["seat-critic"]["active_occupant_id"]
        departed = next(
            o["occupant_id"]
            for o in final["occupants"]
            if o["seat_id"] == "seat-critic" and o["status"] == "departed"
        )
        return {
            "child_rc": child.returncode,
            "resume_rc": resume.returncode,
            "final_status": final["status"],
            "replacement_id": repl,
            "departed_id": departed,
            "replacement_round1": recount(final["ballots"], repl, [1]),
            "departed_round1": recount(final["ballots"], departed, [1]),
            "replacement_later": recount(final["ballots"], repl, [2, 3]),
            "hung": False,
        }


def in_process_crash_control() -> dict | str:
    """Caught-exception path must also recover, not hang."""
    from council.simulate import run_until_complete

    st = initial_state()
    try:
        st = run_until_complete(
            st,
            crash={"round": 2, "seat_id": "seat-critic", "phase": "mid_turn"},
        )
    except Exception as exc:  # noqa: BLE001
        return f"in-process crash raised {type(exc).__name__}: {exc}"
    if st["status"] != "complete":
        return f"in-process status={st['status']!r}"
    return {"status": st["status"], "events": [e["kind"] for e in st["events"]]}


def main() -> int:
    part = partition_and_poison_trap()
    if isinstance(part, str):
        return _fail(part)
    if part["a16_hits_chair"] < 1:
        return _fail(
            "detector control failed: chair context missing A16 canary",
            part,
        )
    if part["a16_hits_replacement"] != 0:
        return _fail(
            "A16 canary leaked into replacement critic context",
            {
                "hits": part["a16_hits_replacement"],
                "context": part["replacement_context"],
            },
        )
    if part["allowed_hits_replacement"] < 1:
        return _fail(
            "detector control failed: allowed canary not found in critic context",
            part,
        )
    if part["partition_ids"] != part["mandate"]:
        return _fail(
            "replacement partition != role mandate",
            {"got": part["partition_ids"], "want": part["mandate"]},
        )
    if not part["poisoned_departed_cache_has_canary"]:
        return _fail("poison trap did not take; cannot prove cache non-inheritance")
    if part["ballots_unattended"] != 0:
        return _fail("replacement carried round-1 ballots", part)

    crash = crash_kill_and_resume()
    if isinstance(crash, str):
        return _fail(crash)
    if crash["replacement_round1"] != 0:
        return _fail("crash-path replacement inherited round-1 ballots", crash)
    if crash["departed_round1"] != 1:
        return _fail("crash-path dropped departed round-1 ballot", crash)
    if crash["replacement_later"] < 1:
        return _fail("crash-path replacement never voted after resume", crash)

    ipc = in_process_crash_control()
    if isinstance(ipc, str):
        return _fail(ipc)
    if "crash" not in ipc["events"] or "replacement" not in ipc["events"]:
        return _fail("in-process path missing crash/replacement events", ipc)

    out = {
        "pass": True,
        "probe": "probe2-partition-crash",
        "unit_id": "TST-0278",
        "a16_canary": A16_CANARY,
        "a16_allowed_canary": A16_ALLOWED_CANARY,
        "a16_hits_replacement": part["a16_hits_replacement"],
        "a16_hits_chair": part["a16_hits_chair"],
        "allowed_hits_replacement": part["allowed_hits_replacement"],
        "replacement_partition": part["partition_ids"],
        "role_mandate": part["mandate"],
        "poisoned_predecessor_cache_not_inherited": True,
        "crash_child_rc": crash["child_rc"],
        "crash_resume_status": crash["final_status"],
        "crash_hung": crash["hung"],
        "crash_replacement_round1_ballots": crash["replacement_round1"],
        "independent_recount": True,
        "in_process_crash_recovered": True,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print(
        "a16_replacement_hits",
        part["a16_hits_replacement"],
        "chair_hits",
        part["a16_hits_chair"],
        "partition",
        part["partition_ids"],
    )
    print(
        "crash_child_rc",
        crash["child_rc"],
        "resume",
        crash["final_status"],
        "repl_r1",
        crash["replacement_round1"],
    )
    print("SUCCESS:TST-0278-probe2 A16 partition canary and crash-path recovery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
