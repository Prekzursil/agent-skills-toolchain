#!/usr/bin/env python3
"""Probe 2: reviewed justification PASSES; empty and boilerplate stay UNJUSTIFIED.

Independent re-derivation of the justification path. Does not trust the
receipt copy of the verdicts; recomputes then compares.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import cochange as C  # noqa: E402

ART = REPO / C.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{C.UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    live = C.run_named_scenarios()
    if not live["all_pass"]:
        return fail(f"live scenarios {live['tests']}")

    legit = live["scenarios"]["legitimate"]
    empty = live["scenarios"]["empty_justification"]
    boiler = live["scenarios"]["boilerplate"]

    if legit["verdict"] != "PASS":
        return fail(f"legitimate verdict={legit['verdict']}")
    pair = legit["intersection"][0]
    if pair["justification_class"] != "JUSTIFIED":
        return fail(f"legitimate class={pair['justification_class']}")
    if len((pair["justification"] or "").strip()) < C.MIN_EXPLICIT:
        return fail("legitimate justification not recorded")
    if not (pair["reviewed_by"] or "").strip():
        return fail("legitimate reviewed_by missing")

    if empty["verdict"] != "FLAGGED":
        return fail(f"empty verdict={empty['verdict']}")
    if empty["intersection"][0]["unjustified_reason"] != "empty":
        return fail(
            f"empty reason={empty['intersection'][0]['unjustified_reason']}"
        )

    if boiler["verdict"] != "FLAGGED":
        return fail(f"boilerplate verdict={boiler['verdict']}")
    if boiler["intersection"][0]["unjustified_reason"] != "boilerplate":
        return fail(
            f"boilerplate reason={boiler['intersection'][0]['unjustified_reason']}"
        )

    empty_class, empty_reason = C.classify_justification(
        "", "TST-0340-adversarial-reviewer"
    )
    boiler_class, boiler_reason = C.classify_justification(
        "update snapshots", "TST-0340-adversarial-reviewer"
    )
    ok_class, ok_reason = C.classify_justification(
        pair["justification"], pair["reviewed_by"]
    )
    if (empty_class, empty_reason) != ("UNJUSTIFIED", "empty"):
        return fail(f"classify empty {(empty_class, empty_reason)}")
    if (boiler_class, boiler_reason) != ("UNJUSTIFIED", "boilerplate"):
        return fail(f"classify boilerplate {(boiler_class, boiler_reason)}")
    if (ok_class, ok_reason) != ("JUSTIFIED", None):
        return fail(f"classify reviewed {(ok_class, ok_reason)}")

    art = doc.get("scenarios") or {}
    if (art.get("legitimate") or {}).get("verdict") != "PASS":
        return fail("receipt legitimate not PASS")
    rec_pair = ((art.get("legitimate") or {}).get("intersection") or [{}])[0]
    if rec_pair.get("justification") != pair["justification"]:
        return fail("receipt did not record the reviewed justification")
    if (art.get("empty_justification") or {}).get("verdict") != "FLAGGED":
        return fail("receipt empty not FLAGGED")
    if (art.get("boilerplate") or {}).get("verdict") != "FLAGGED":
        return fail("receipt boilerplate not FLAGGED")

    print(
        json.dumps(
            {
                "probe": "probe2-justification",
                "legitimate_verdict": legit["verdict"],
                "legitimate_class": pair["justification_class"],
                "empty_reason": empty["intersection"][0]["unjustified_reason"],
                "boilerplate_reason": boiler["intersection"][0]["unjustified_reason"],
                "reviewed_by": pair["reviewed_by"],
                "receipt_matches": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"SUCCESS:{C.UNIT}-probe2 legitimate JUSTIFIED and recorded; "
        "empty+boilerplate UNJUSTIFIED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
