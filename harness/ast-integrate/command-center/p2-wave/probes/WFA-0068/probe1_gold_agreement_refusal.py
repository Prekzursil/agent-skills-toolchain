#!/usr/bin/env python3
"""Probe 1: per-disposition gold agreement + missing-input refusal both-states.

Re-runs the author classifier on the frozen gold set. Does not trust the
artifact's stored accuracy number until the live per-disposition rates meet
the pre-registered floor. Aggregate accuracy is printed and is not the gate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from agreement import AGREEMENT_FLOOR, passes_floor, per_disposition  # noqa: E402
from decide import decide  # noqa: E402
from gold_set import gold_records, restored_license_adopt  # noqa: E402
from vocabulary import VOCABULARY  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0068-disposition-decision-procedure.json"
SENTINEL = "SUCCESS:WFA-0068"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0068-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if list(doc.get("vocabulary") or []) != list(VOCABULARY):
        return fail("vocabulary drifted")
    if float(doc.get("agreement_floor")) != AGREEMENT_FLOOR:
        return fail("agreement floor drifted")

    rows = gold_records()
    if len(rows) != 20:
        return fail(f"gold n={len(rows)}")
    gold = [str(r["gold"]) for r in rows]
    pred = []
    for rec in rows:
        got = decide(rec)
        pred.append(str(got["disposition"]))
        print(
            f"{rec['id']} family={rec['family']} gold={rec['gold']} "
            f"pred={got['disposition']} reason={got['reason']} fired={got['fired']}"
        )
        if got["disposition"] != rec["gold"]:
            return fail(f"{rec['id']} {got['disposition']} != gold {rec['gold']}")

    per = per_disposition(gold, pred)
    for row in per:
        print(
            f"per-disposition {row['disposition']} n_gold={row['n_gold']} "
            f"n_pred={row['n_pred']} recall={row['recall']} kappa={row['kappa']} "
            f"meets_floor={row['meets_floor']}"
        )
        stored = next(
            (
                s
                for s in (doc.get("per_disposition_agreement") or [])
                if s.get("disposition") == row["disposition"]
            ),
            None,
        )
        if not stored:
            return fail(f"artifact missing per-disposition row {row['disposition']}")
        if stored.get("n_gold") != row["n_gold"] or stored.get("n_true_positive") != row["n_true_positive"]:
            return fail(f"artifact drift {row['disposition']}")
    if not passes_floor(per):
        return fail("per-disposition floor")
    rare = [r for r in per if r["n_gold"] == 1]
    if len(rare) < 6:
        return fail(f"rare dispositions hidden n={len(rare)}")
    if any(r["meets_floor"] is not True for r in rare):
        return fail("rare disposition below floor")

    missing = next(r for r in rows if r["id"] == "GOLD-09")
    refusal = decide(missing)
    print(
        f"refusal GOLD-09 disposition={refusal['disposition']} "
        f"reason={refusal['reason']} missing={refusal['missing_input']}"
    )
    if refusal["disposition"] != "UNKNOWN-NEEDS-PROBE":
        return fail("refusal did not trigger")
    if refusal["reason"] != "required-input-refusal":
        return fail("refusal reason")
    if refusal["missing_input"] != "license":
        return fail(f"missing_input={refusal['missing_input']}")

    restored = decide(restored_license_adopt())
    print(
        f"both-states restored disposition={restored['disposition']} "
        f"reason={restored['reason']}"
    )
    if restored["disposition"] == "UNKNOWN-NEEDS-PROBE":
        return fail("restored license still UNKNOWN")
    if restored["disposition"] != "ADOPT-AS-IS":
        return fail(f"restored {restored['disposition']}")

    print("SUCCESS:WFA-0068-probe1 per-disposition agreement and refusal both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
