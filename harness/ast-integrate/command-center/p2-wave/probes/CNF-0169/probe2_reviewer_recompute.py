#!/usr/bin/env python3
"""Named probe 2: independent recompute of two pairs + remaining controls.

Mechanically different from probe 1: sequential membership walk in reviewer.py,
not differ.ten_pairwise. Recomputes catalog|receipts and artifacts|catalog.
Also requires duplicate-id and empty-input controls to fire.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import controls as C  # noqa: E402
import differ as D  # noqa: E402
import reviewer as R  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0169.json"
REVIEW_PAIRS = (("catalog", "receipts"), ("artifacts", "catalog"))


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:CNF-0169-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, default=str)[:3000])
    return 1


def directed_ids(row: dict, left: str, right: str, side: str) -> tuple[int, str]:
    payload = row.get(side) or {}
    return int(payload.get("count") or 0), str(payload.get("digest") or "")


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0169" not in json.dumps(doc):
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail("self-declared", doc.get("state"))

    ctrls = C.assert_controls()
    by_id = {r["id"]: r for r in ctrls["controls"]}
    if not by_id["duplicate-id"]["fired_on_bad_state"]:
        return fail("duplicate-id silent", by_id["duplicate-id"])
    if not by_id["empty-input"]["reports_total_divergence"]:
        return fail("empty-input did not report divergence", by_id["empty-input"])
    if by_id["empty-input"].get("false_agreement"):
        return fail("empty-input false agreement")

    live = D.load_live(REPO)
    sets = {name: set(live["sets"][name]) for name in D.SOURCES}
    art_pairs = {row["pair"]: row for row in (doc.get("pairwise_differences") or [])}
    recomputed = []
    for left, right in REVIEW_PAIRS:
        indep = R.both_directions(sets[left], sets[right])
        art = art_pairs.get(f"{left}|{right}") or art_pairs.get(f"{right}|{left}")
        if not art:
            return fail("artifact missing pair", f"{left}|{right}")
        # Map independent left/right onto artifact orientation.
        if art["left"] == left:
            art_lmr, art_rml = art["left_minus_right"], art["right_minus_left"]
            indep_lmr, indep_rml = (
                indep["left_minus_right"],
                indep["right_minus_left"],
            )
        else:
            art_lmr, art_rml = art["left_minus_right"], art["right_minus_left"]
            indep_lmr, indep_rml = (
                indep["right_minus_left"],
                indep["left_minus_right"],
            )
        live_row = D.pair_row(live["pairwise_differences"], left, right)
        if D.digest_ids(indep_lmr) != art_lmr.get("digest"):
            return fail("reviewer digest mismatch l-r", {"pair": f"{left}|{right}"})
        if D.digest_ids(indep_rml) != art_rml.get("digest"):
            return fail("reviewer digest mismatch r-l", {"pair": f"{left}|{right}"})
        if len(indep_lmr) != art_lmr.get("count") or len(indep_rml) != art_rml.get("count"):
            return fail("reviewer count mismatch", {"pair": f"{left}|{right}"})
        if live_row["symmetric_count"] != indep["symmetric_count"]:
            return fail("reviewer vs live symmetric drift", {"pair": f"{left}|{right}"})
        recomputed.append(
            {
                "pair": f"{left}|{right}",
                "left_minus_right_count": len(indep["left_minus_right"]),
                "right_minus_left_count": len(indep["right_minus_left"]),
                "match": True,
            }
        )

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        return fail("reviewer not independent")
    if reviewer.get("verdict") != "PASS":
        return fail("reviewer verdict", reviewer.get("verdict"))

    if doc.get("five_way_agree") is True:
        return fail("five_way_agree overclaim")

    payload = {
        "pass": True,
        "probe": "probe2-reviewer-recompute",
        "unit_id": "CNF-0169",
        "recomputed": recomputed,
        "duplicate_id_fired": True,
        "empty_input_divergence": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:CNF-0169-probe2 independent-pairs duplicate-empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
