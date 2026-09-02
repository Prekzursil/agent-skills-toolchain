#!/usr/bin/env python3
"""Probe 1: stale vs current (both-states), injected clock, deterministic.

Signal 1: a certificate whose corpus_version is superseded reports STALE.
Signal 2: the same certificate against the live corpus reports VALID.
Clock is injected (NOW); admit.py must not read the wall clock.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import admit as A  # noqa: E402
import fixtures as F  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0203.json"


def _src_uses_wall_clock() -> bool:
    src = (HERE / "admit.py").read_text(encoding="utf-8")
    banned = ("datetime.now", "time.time(", "date.today", "utcnow(")
    return any(tok in src for tok in banned)


def main() -> int:
    if _src_uses_wall_clock():
        print("FAILED:IMP-0203-probe1 admit.py reads the wall clock")
        return 1

    rec = F.current_record()
    pair = A.both_states_corpus(
        rec,
        live_spec_version=F.SPEC_CURRENT,
        now=F.NOW,
        superseded_corpus=F.CORPUS_SUPERSEDED,
    )
    current = pair["current"]
    stale = pair["superseded"]

    print(json.dumps({"current": current, "superseded": stale}, sort_keys=True))

    if current["status"] != A.VALID:
        print(f"FAILED:IMP-0203-probe1 current status={current['status']} want=VALID")
        return 1
    if current["reasons"]:
        print(f"FAILED:IMP-0203-probe1 current not silent reasons={current['reasons']}")
        return 1
    if stale["status"] != A.STALE:
        print(f"FAILED:IMP-0203-probe1 superseded status={stale['status']} want=STALE")
        return 1
    if A.REASON_CORPUS not in stale["reasons"]:
        print(f"FAILED:IMP-0203-probe1 superseded reasons={stale['reasons']}")
        return 1
    if stale["now"] != F.NOW or current["now"] != F.NOW:
        print("FAILED:IMP-0203-probe1 clock was not the injected NOW")
        return 1

    again = A.both_states_corpus(
        rec,
        live_spec_version=F.SPEC_CURRENT,
        now=F.NOW,
        superseded_corpus=F.CORPUS_SUPERSEDED,
    )
    if again != pair:
        print("FAILED:IMP-0203-probe1 evaluation is not deterministic")
        return 1

    spec_stale = A.evaluate(
        rec,
        live_corpus_version=F.CORPUS_CURRENT,
        live_spec_version=F.SPEC_SUPERSEDED,
        now=F.NOW,
    )
    if spec_stale["status"] != A.STALE or A.REASON_SPEC not in spec_stale["reasons"]:
        print(f"FAILED:IMP-0203-probe1 spec superseded {spec_stale}")
        return 1

    expired = A.evaluate(
        rec,
        live_corpus_version=F.CORPUS_CURRENT,
        live_spec_version=F.SPEC_CURRENT,
        now=F.EXPIRY_PAST if False else rec["expiry"],
    )
    # now == expiry => STALE (inclusive expiry)
    if expired["status"] != A.STALE or A.REASON_EXPIRED not in expired["reasons"]:
        print(f"FAILED:IMP-0203-probe1 expiry at now {expired}")
        return 1

    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0203-probe1 catalog receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0203-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0203" not in text:
        print("FAILED:IMP-0203-probe1 sentinel absent")
        return 1

    print("fired_on_bad=True silent_on_good=True injected_clock=True deterministic=True")
    print("SUCCESS:IMP-0203-probe1 stale corpus STALE; current VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
