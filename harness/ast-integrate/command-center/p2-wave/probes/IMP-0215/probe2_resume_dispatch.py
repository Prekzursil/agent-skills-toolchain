#!/usr/bin/env python3
"""IMP-0215 probe 2: resume does not repeat proven work.

Two independent signals, counted from the ledger (not from the runner's
self-report):
  (1) kill-at-30% then resume dispatches strictly fewer claims than a
      clean run; resume dispatch ids are disjoint from killed proven ids
  (2) a naive restart-from-zero after the same kill re-dispatches the
      full roster (dispatch count not lower) — the skip is load-bearing
Oracle both-states: tampering a proven receipt hash forces that claim to
be re-dispatched on resume.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from workflow_foundry.resumable import (  # noqa: E402
    InterruptedRun,
    ResumableEngine,
    STAGES,
    count_ledger_dispatches,
    load_artifact,
    atomic_write_json,
)

GOAL = "IMP-0215-resume-dispatch-goal"
ENGINE = "forge"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0215-probe2 {msg}")
    return 1


def kill_then(root: Path, *, session_prefix: str) -> ResumableEngine:
    runner = ResumableEngine(root, ENGINE, goal=GOAL)
    try:
        runner.run(session=f"{session_prefix}-killed", kill_at_pct=30)
    except InterruptedRun:
        return runner
    raise RuntimeError("expected interrupt")


def main() -> int:
    stages = [s["id"] for s in STAGES[ENGINE]]
    with tempfile.TemporaryDirectory(prefix="imp0215-p2-") as tmp:
        tmp_path = Path(tmp)

        clean = ResumableEngine(tmp_path / "clean", ENGINE, goal=GOAL)
        clean_summary = clean.run(session="clean")
        clean_n, clean_ids = count_ledger_dispatches(clean.ledger_path, session="clean")
        if clean_n != len(stages) or clean_ids != stages:
            return fail(f"clean dispatch {clean_ids} want {stages}")
        if clean_summary["state"] != "COMPLETE":
            return fail(f"clean state={clean_summary['state']}")

        resumed = kill_then(tmp_path / "resume", session_prefix="resume")
        killed_n, killed_ids = count_ledger_dispatches(
            resumed.ledger_path, session="resume-killed"
        )
        if killed_n != 3:
            return fail(f"killed dispatch count {killed_n} want 3 ids={killed_ids}")
        partial = load_artifact(resumed.artifact_path)
        proven = [c["id"] for c in partial["claims"] if c["verdict"] == "PROVEN"]
        if proven != killed_ids:
            return fail(f"ledger killed ids {killed_ids} != artifact proven {proven}")

        resume_summary = resumed.run(session="resume", resume=True)
        resume_n, resume_ids = count_ledger_dispatches(
            resumed.ledger_path, session="resume"
        )
        if resume_n >= clean_n:
            return fail(
                f"resume dispatch count {resume_n} not strictly lower than clean {clean_n}"
            )
        if resume_n != 7:
            return fail(f"resume dispatch count {resume_n} want 7 ids={resume_ids}")
        overlap = set(resume_ids) & set(killed_ids)
        if overlap:
            return fail(f"resume re-did proven work {sorted(overlap)}")
        if set(resume_ids) | set(killed_ids) != set(stages):
            return fail("resume+killed did not cover the roster")
        if resume_summary["state"] != "COMPLETE":
            return fail(f"resume state={resume_summary['state']}")
        skip_n, skip_ids = count_ledger_dispatches(resumed.ledger_path, session=None)
        # Independent skip events: count skip_proven lines ourselves.
        skip_events = []
        for line in resumed.ledger_path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if rec.get("event") == "skip_proven" and rec.get("session") == "resume":
                skip_events.append(rec.get("claim_id"))
        if skip_events != killed_ids:
            return fail(f"skip_proven {skip_events} != killed {killed_ids}")

        naive = kill_then(tmp_path / "naive", session_prefix="naive")
        naive.run(session="naive-restart", resume=False, ignore_checkpoint=True)
        naive_n, naive_ids = count_ledger_dispatches(
            naive.ledger_path, session="naive-restart"
        )
        if naive_n < clean_n:
            return fail(
                f"naive restart dispatch {naive_n} was lower; negative control silent"
            )
        if naive_n != clean_n or naive_ids != stages:
            return fail(f"naive restart ids {naive_ids} want full roster")

        tamper = kill_then(tmp_path / "oracle", session_prefix="oracle")
        doc = load_artifact(tamper.artifact_path)
        target = doc["claims"][0]
        original_hash = target["receipt_hash"]
        target["receipt_hash"] = "0" * 64
        atomic_write_json(tamper.artifact_path, doc)
        tamper.run(session="oracle-resume", resume=True)
        oracle_n, oracle_ids = count_ledger_dispatches(
            tamper.ledger_path, session="oracle-resume"
        )
        if target["id"] not in oracle_ids:
            return fail("tampered proven claim was skipped; oracle is vacuous")
        if oracle_n != 8:
            return fail(
                f"oracle-resume dispatch {oracle_n} ids={oracle_ids} want 8 "
                "(1 tampered + 7 unknown)"
            )
        if original_hash == "0" * 64:
            return fail("tamper did not change the hash")

        final = load_artifact(resumed.artifact_path)
        clean_doc = load_artifact(clean.artifact_path)
        resume_payloads = {
            c["id"]: c["payload"]["result_digest"] for c in final["claims"]
        }
        clean_payloads = {
            c["id"]: c["payload"]["result_digest"] for c in clean_doc["claims"]
        }
        if resume_payloads != clean_payloads:
            return fail("resumed payloads drifted from clean run")

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe2-resume-dispatch",
                "unit_id": "IMP-0215",
                "clean_dispatch_count": clean_n,
                "killed_dispatch_count": killed_n,
                "resume_dispatch_count": resume_n,
                "resume_strictly_lower": resume_n < clean_n,
                "resume_ids": resume_ids,
                "killed_ids": killed_ids,
                "overlap": [],
                "naive_restart_dispatch_count": naive_n,
                "naive_not_lower": naive_n >= clean_n,
                "oracle_resume_dispatch_count": oracle_n,
                "oracle_redispatched_tampered": True,
                "skip_proven": skip_events,
            },
            sort_keys=True,
        )
    )
    print(
        f"clean={clean_n} killed={killed_n} resume={resume_n} "
        f"naive={naive_n} oracle={oracle_n} skip={len(skip_events)}"
    )
    unused = skip_n  # ledger total including skips; keeps the parse live
    print(
        f"SUCCESS:IMP-0215-probe2 resume dispatch {resume_n}<{clean_n} "
        f"ledger_events={unused}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
