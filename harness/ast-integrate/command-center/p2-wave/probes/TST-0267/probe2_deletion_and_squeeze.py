#!/usr/bin/env python3
"""Probe 2: independent both-states deletion control + summarisation squeeze.

Does not trust probe1's PASS flag. Re-renders the chain, searches UTF-8
bytes for the token, then:

  * GOOD: propagate_dissent on -> token and claim in every stage
  * BAD:  propagate_dissent removed -> trace FAIL at argument_ledger
  * SQUEEZE: a cap smaller than the minority block is rejected; a cap
    that fits the block keeps the dissent while truncating filler
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from tools.council import simulate as S  # noqa: E402
from tools.council import synthesis as Y  # noqa: E402
from tools.council.synthesis import CapRejected  # noqa: E402

FIXTURE = HERE / "fixtures" / "lone-dissenter.json"
AGGRESSIVE_CAP = 80
GENEROUS_CAP = 10000


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0267-probe2 {msg}")
    return 1


def independent_present(text: str, token: str, claim: str) -> dict:
    """Byte search that does not call trace_survival."""
    raw = text.encode("utf-8")
    tok_off = raw.find(token.encode("utf-8"))
    clm_off = raw.find(claim.encode("utf-8"))
    return {
        "present": tok_off >= 0 and clm_off >= 0,
        "token_byte_offset": tok_off,
        "claim_byte_offset": clm_off,
    }


def independent_walk(rendered: dict[str, str]) -> dict:
    first_missing = None
    rows = []
    for stage in Y.STAGE_IDS:
        hit = independent_present(rendered[stage], S.DISSENT_TOKEN, S.DISSENT_CLAIM)
        if not hit["present"] and first_missing is None:
            first_missing = stage
        rows.append({"artifact": stage, **hit})
    return {"ok": first_missing is None, "first_missing": first_missing, "stages": rows}


def main() -> int:
    spec = S.load_spec(FIXTURE)
    transcript = S.run(spec)

    good_chain = Y.run_chain(transcript, propagate=True, max_body_chars=None)
    good = independent_walk(good_chain["rendered"])
    if not good["ok"]:
        return _fail(f"good state dropped dissent at {good['first_missing']}")

    bad_chain = Y.run_chain(transcript, propagate=False, max_body_chars=None)
    bad = independent_walk(bad_chain["rendered"])
    if bad["ok"]:
        return _fail("deletion control did not fire; trace still green without propagate_dissent")
    if bad["first_missing"] != "argument_ledger":
        return _fail(f"expected drop at argument_ledger, got {bad['first_missing']}")
    # Transcript is produced by the simulator, not the propagation step.
    if not bad["stages"][0]["present"]:
        return _fail("deletion control also blanked the transcript; probe is not selective")

    rejected = False
    reject_stage = None
    reject_detail = None
    try:
        Y.run_chain(transcript, propagate=True, max_body_chars=AGGRESSIVE_CAP)
    except CapRejected as exc:
        rejected = True
        reject_stage = exc.stage
        reject_detail = str(exc)
    if not rejected:
        return _fail("aggressive cap was accepted; dissent could be silently squeezed out")

    generous = Y.run_chain(transcript, propagate=True, max_body_chars=GENEROUS_CAP)
    generous_walk = independent_walk(generous["rendered"])
    if not generous_walk["ok"]:
        return _fail(f"generous cap still dropped dissent at {generous_walk['first_missing']}")

    # Body truncation must not eat the minority block when the cap fits it.
    squeezed_exec = generous["rendered"]["executive_summary"]
    if S.DISSENT_TOKEN not in squeezed_exec or S.DISSENT_CLAIM not in squeezed_exec:
        return _fail("executive summary lost dissent under a fitting cap")

    out = {
        "deletion": {
            "bad_first_missing": bad["first_missing"],
            "fired_on_bad_state": True,
            "good_first_missing": None,
            "silent_on_good_state": True,
            "transcript_still_has_dissent": True,
        },
        "pass": True,
        "probe": "probe2-deletion-and-squeeze",
        "squeeze": {
            "aggressive_cap": AGGRESSIVE_CAP,
            "aggressive_rejected": True,
            "generous_cap": GENEROUS_CAP,
            "generous_survived": True,
            "reject_detail": reject_detail,
            "reject_stage": reject_stage,
        },
        "unit_id": "TST-0267",
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print("SUCCESS:TST-0267-probe2 deletion fires; squeeze rejects or preserves dissent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
