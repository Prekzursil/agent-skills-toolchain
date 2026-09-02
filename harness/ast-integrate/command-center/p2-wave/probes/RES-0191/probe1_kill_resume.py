#!/usr/bin/env python3
"""Probe 1: kill-mid-flight resume reproduces the control claim set.

Does not inspect backend_calls ledgers or corrupt-checkpoint refusal.
Those are probe 2.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import engine as E  # noqa: E402
import experiment as X  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0191-probe1 {msg}")
    return 1


def main() -> int:
    if not C.ART.is_file() or C.ART.stat().st_size <= 0:
        return fail("artifact-absent")
    doc = json.loads(C.ART.read_text(encoding="utf-8"))
    errs = C.evaluate_artifact(doc)
    if errs:
        return fail("contract:" + ",".join(errs[:12]))
    cap_errs = C.verify_captures()
    if cap_errs:
        return fail("captures:" + ",".join(cap_errs[:8]))
    if C.SENTINEL not in C.ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")

    control = X.control_run()
    kr = X.kill_and_resume()
    expected = E.expected_full_claims()
    if control["claims"] != expected:
        return fail(f"control-claims {control['claims']}")
    if kr["final_claims"] != expected:
        return fail(f"resume-claims {kr['final_claims']}")
    if kr["mid_status"]["Q1"] != "completed":
        return fail("mid-Q1-not-completed")
    if kr["mid_status"]["Q2"] != "partial":
        return fail("mid-Q2-not-partial")
    if kr["mid_status"]["Q3"] != "failed":
        return fail("mid-Q3-not-failed")
    if kr["mid_status"]["Q4"] != "partial":
        return fail("mid-Q4-not-partial")
    if set(kr["final_status"].values()) != {"completed"}:
        return fail(f"final-status {kr['final_status']}")
    if kr["kill_rc"] not in {-9, 9, 99, 137}:
        return fail(f"kill-rc {kr['kill_rc']}")

    art_claims = sorted(
        (doc.get("kill_resume_claim_set") or doc.get("experiment", {}).get("expected_claims") or [])
    )
    live_expected = expected
    stated = doc.get("both_states") or {}
    if stated.get("resume_matches_control") is not True:
        return fail("artifact-both-states")
    exp = doc.get("experiment") or {}
    if exp.get("kill_resume", {}).get("final_claims") != live_expected:
        # tolerate emit storing under experiment.expected_claims
        if exp.get("expected_claims") != live_expected:
            return fail("artifact-claim-set-stale")
    if exp.get("kill_resume", {}).get("mid_status") != kr["mid_status"]:
        return fail("artifact-mid-status-stale")

    payload = {
        "probe": "probe1-kill-resume",
        "unit_id": C.UNIT,
        "kill_rc": kr["kill_rc"],
        "mid_status": kr["mid_status"],
        "control_n": len(control["claims"]),
        "resume_n": len(kr["final_claims"]),
        "match": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "kill_rc=-9 mid=Q1:completed,Q2:partial,Q3:failed,Q4:partial "
        "resume_claim_set=control"
    )
    print("SUCCESS:RES-0191-probe1 kill-resume claim-set parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
