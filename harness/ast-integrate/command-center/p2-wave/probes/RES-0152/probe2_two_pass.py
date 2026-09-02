#!/usr/bin/env python3
"""Probe 2: two independent counters agree on the frozen sample; live matches artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import load_definition, measure  # noqa: E402

REPO = HERE.parents[3]
ART = (
    REPO
    / "command-center"
    / "research"
    / "evidence-quality"
    / "RES-0152-confidence-band-calibration-set.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0152-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    definition = load_definition()
    live = measure()
    tp = live["two_pass"]
    if tp["relative_delta"] > 0.10:
        return fail(
            f"two-pass delta {tp['relative_delta']} exceeds 10% "
            f"(a={tp['pass_a_count']} b={tp['pass_b_count']})"
        )
    if not tp["within_10_percent"]:
        return fail("within_10_percent flag is false")
    corr = tp.get("catalog_path_corroboration") or {}
    if not corr.get("pass"):
        return fail(
            "frozen paths missing from catalog bytes: "
            + ",".join((corr.get("missing") or [])[:5])
        )
    art_tp = doc.get("two_pass") or {}
    if art_tp.get("pass_a_count") != tp["pass_a_count"] or art_tp.get(
        "pass_b_count"
    ) != tp["pass_b_count"]:
        return fail(
            "artifact two-pass counts drifted from live re-count "
            f"art=({art_tp.get('pass_a_count')},{art_tp.get('pass_b_count')}) "
            f"live=({tp['pass_a_count']},{tp['pass_b_count']})"
        )
    if live["definition_sha256"] != (doc.get("definition") or {}).get("sha256"):
        return fail("live definition hash drifted from artifact")

    cal = doc.get("calibration") or {}
    if cal.get("n_scored_forward") != live["n_scored_forward"]:
        return fail(
            "n_scored_forward drifted "
            f"art={cal.get('n_scored_forward')} live={live['n_scored_forward']}"
        )
    if cal.get("n_held_forward") != live["n_held_forward"]:
        return fail("n_held_forward drifted")
    if live["n_scored_forward"] < 60:
        return fail("live scored forward-looking known outcomes < 60")
    live_likely = live["likely"]
    art_likely = cal.get("likely") or {}
    if live_likely.get("status") != art_likely.get("status"):
        return fail("likely-band status drifted from live re-count")
    if live_likely.get("n") != art_likely.get("n"):
        return fail("likely-band n drifted from live re-count")

    if tp["pass_a_count"] < 60:
        return fail("pass-A held count < 60")
    if int(tp.get("frozen_n") or 0) < 60:
        return fail("frozen sample < 60")
    if len(definition.get("frozen_catalog_claims") or []) < 60:
        return fail("DEFINITION frozen_catalog_claims < 60")

    payload = {
        "probe": "probe2-two-pass-agreement",
        "unit_id": "RES-0152",
        "pass_a_count": tp["pass_a_count"],
        "pass_b_count": tp["pass_b_count"],
        "relative_delta": tp["relative_delta"],
        "within_10_percent": True,
        "n_scored_forward": live["n_scored_forward"],
        "likely_n": live_likely["n"],
        "likely_status": live_likely["status"],
        "frozen_n": tp.get("frozen_n"),
        "catalog_path_corroboration": bool(corr.get("pass")),
        "live_matches_artifact": True,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "SUCCESS:RES-0152-probe2 two-pass counts agree within 10%; "
        "live re-count matches artifact headline"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
