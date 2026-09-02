#!/usr/bin/env python3
"""Probe 2: independent adversarial recount + grind re-check.

Does not call progress.classify_attempts. Reimplements grind as trailing
fingerprint equality. Re-runs harvest.census() and compares the printed
success-by-attempt row. Defaults to REFUTED.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harvest as H  # noqa: E402

ART = REPO / (
    "command-center/research/deep-research-design/"
    "RES-0167-fix-review-repair-loop-limits.json"
)
SENTINEL = "SUCCESS:RES-0167"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
GRIND_FP = "partial-clone-hydration-transport"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0167-probe2 {msg}")
    return 1


def independent_grind(attempts: list[dict]) -> str:
    """Independent classifier: last two non-empty equal fingerprints → NO-PROGRESS."""
    if not attempts:
        return "REFUSE"
    last = attempts[-1]
    if str(last.get("outcome") or "").upper() in {"SUCCESS", "DELIVERED", "PASS"}:
        return "PROGRESS"
    if len(attempts) < 2:
        return "PROGRESS"
    fa = str(attempts[-2].get("error_fingerprint") or "").strip()
    fb = str(attempts[-1].get("error_fingerprint") or "").strip()
    if fa and fb and fa == fb:
        return "NO-PROGRESS"
    return "PROGRESS"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {exc}")
    if doc.get("unit_id") != "RES-0167":
        return fail(f"unit_id {doc.get('unit_id')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")

    grind = [
        {"attempt": 1, "error_fingerprint": GRIND_FP, "outcome": "TIMEOUT"},
        {"attempt": 2, "error_fingerprint": GRIND_FP, "outcome": "FAILED"},
    ]
    productive = [
        {
            "attempt": 1,
            "error_fingerprint": "probe1-json-lone-surrogate-serialization",
            "outcome": "FAILED",
        },
        {
            "attempt": 2,
            "error_fingerprint": "probe1-discovery-read-toctou",
            "outcome": "FAILED",
        },
    ]
    g = independent_grind(grind)
    p = independent_grind(productive)
    if g != "NO-PROGRESS":
        return fail(f"independent grind {g}")
    if p != "PROGRESS":
        return fail(f"independent productive {p}")
    mutant = deepcopy(grind)
    mutant[-1]["error_fingerprint"] = "different-class"
    if independent_grind(mutant) != "PROGRESS":
        return fail("independent checker stuck on NO-PROGRESS after fingerprint change")
    if "PROGRESS" == g:
        return fail("always-PROGRESS not distinguishable from independent grind")

    live = H.census()
    printed_live = live["printed_success_by_attempt"]
    printed_art = doc.get("printed_success_by_attempt")
    if printed_art != printed_live:
        return fail(
            f"success-by-attempt drift artifact={printed_art!r} live={printed_live!r}"
        )
    s1 = live["signal1_supervisor"]
    if int(s1["second_attempt_successes"]) != 0:
        return fail("unexpected attempt-2 successes in supervisor census")
    pairs = live["signal2_tree"]["two_strike_pairs"]
    if int(pairs["delivered_after_two_strikes"]) != 0:
        return fail("two-strike pairs converted; harvest claim would be stale")
    seq = live["signal2_tree"]["retry_sequences"]
    if int(seq["trailing_same_fingerprint_then_success"]) != 0:
        return fail("same-fingerprint retry converted to success; claim stale")

    payload = {
        "probe": "probe2-independent-recount",
        "unit_id": "RES-0167",
        "reviewer_verdict": "PASS",
        "independent_grind": g,
        "independent_productive": p,
        "printed_success_by_attempt": printed_live,
        "second_attempt_successes": s1["second_attempt_successes"],
        "two_strike_delivered": pairs["delivered_after_two_strikes"],
        "same_fp_then_success": seq["trailing_same_fingerprint_then_success"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "INDEPENDENT WALKER: trailing-equal fingerprints => NO-PROGRESS; "
        "changed fingerprints => PROGRESS; harvest reprint matches artifact."
    )
    print("SUCCESS:RES-0167-probe2 independent recount and grind walker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
