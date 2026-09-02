#!/usr/bin/env python3
"""Probe 2: pay ledger + corrupt refuse + naive-skip mutant.

Does not use control-vs-resume claim-set equality as its pass criterion.
That is probe 1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import experiment as X  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0191-probe2 {msg}")
    return 1


def main() -> int:
    if not C.ART.is_file():
        return fail("artifact-absent")
    doc = json.loads(C.ART.read_text(encoding="utf-8"))
    if doc.get("state") != "SUCCESS" or C.SENTINEL not in C.ART.read_text(encoding="utf-8"):
        return fail("state-or-sentinel")

    kr = X.kill_and_resume()
    if not kr["q1_not_repaid"]:
        return fail("Q1-repaid-on-resume")
    if not kr["q2_continued"]:
        return fail("Q2-not-continued")
    if not kr["q3_retried"]:
        return fail("Q3-not-retried")
    if not kr["q4_continued"]:
        return fail("Q4-not-continued")
    if kr["mid_pay"]["Q1"] != kr["final_pay"]["Q1"]:
        return fail("Q1-pay-drift")
    if kr["final_pay"]["Q1"] != 2:
        return fail(f"Q1-pay {kr['final_pay']['Q1']}")

    flip = X.corrupt_byte_flip_refuses()
    if not flip["loud"]:
        return fail(f"byte-flip-not-loud rc={flip['rc']} {flip['text'][-300:]}")
    incon = X.corrupt_inconsistent_completed_refuses()
    if not incon["loud"]:
        return fail(f"inconsistent-not-loud rc={incon['rc']} {incon['text'][-300:]}")
    naive = X.naive_mutant_drops_claims()
    if not naive["silent_skip"] or not naive["dropped"]:
        return fail(f"naive-did-not-drop {naive}")

    # Artifact must not overclaim: recorded pay/refuse must match this live run.
    exp = doc.get("experiment") or {}
    art_pay = (exp.get("kill_resume") or {}).get("final_pay") or {}
    if art_pay and art_pay.get("Q1") != kr["final_pay"]["Q1"]:
        return fail("artifact-Q1-pay-stale")
    if (doc.get("both_states") or {}).get("corrupt_refused") is not True:
        return fail("artifact-corrupt-flag")
    if (doc.get("both_states") or {}).get("completed_not_repaid") is not True:
        return fail("artifact-pay-flag")
    if (doc.get("both_states") or {}).get("naive_skip_drops_claims") is not True:
        return fail("artifact-naive-flag")

    # Reviewer rail: this probe is the independent refuter named in the artifact.
    rev = doc.get("reviewer") or {}
    if "probe2" not in str(rev.get("reviewer_id") or ""):
        return fail("reviewer-not-probe2")

    payload = {
        "probe": "probe2-pay-corrupt",
        "unit_id": C.UNIT,
        "q1_pay_mid": kr["mid_pay"]["Q1"],
        "q1_pay_final": kr["final_pay"]["Q1"],
        "flip_rc": flip["rc"],
        "incon_rc": incon["rc"],
        "naive_dropped": naive["dropped"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "Q1_not_repaid=True flip_refused=True inconsistent_refused=True "
        f"naive_dropped={len(naive['dropped'])}"
    )
    print("SUCCESS:RES-0191-probe2 pay-ledger corrupt-refuse naive-skip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
