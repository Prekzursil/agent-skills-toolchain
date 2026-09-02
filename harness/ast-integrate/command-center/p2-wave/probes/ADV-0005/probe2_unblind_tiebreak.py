#!/usr/bin/env python3
"""Probe 2: unblind, diff verdicts, named settling experiment as tiebreak.

Mechanically different from probe 1. Vote counting is banned; the specific
settling probe wins on disagreement. Optional artifact check when present.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402


def main() -> int:
    unb = E.unblind_pass()
    payload = {
        "probe": unb["probe"],
        "unit_id": E.UNIT,
        "vote_counting": unb["vote_counting"],
        "disagreement_count": unb["disagreement_count"],
        "disagreements": unb["disagreements"],
        "calibration_planted_false_refuted": unb["calibration_planted_false_refuted"],
        "calibration_planted_true_confirmed": unb["calibration_planted_true_confirmed"],
        "named_registry_present": unb["named_registry"]["canonical_present"],
        "p0_p1_from_named_registry": unb["named_registry"]["p0_p1_from_named_registry"],
        "finals": [
            {
                "id": r["id"],
                "blind_verdict": r["blind_verdict"],
                "implementer_verdict": r["implementer_verdict"],
                "settling_verdict": r["settling_verdict"],
                "tiebreak": r["tiebreak"],
                "final_verdict": r["final_verdict"],
                "agreed_with_implementer": r["agreed_with_implementer"],
            }
            for r in unb["finals"]
        ],
        "ok": bool(unb["ok"] and unb["vote_counting"] is False),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))

    art = E.REPO / E.OUTPUT_REL
    if art.is_file():
        text = art.read_text(encoding="utf-8")
        doc = json.loads(text)
        ok, why = E.validate_schema(doc)
        print(f"artifact_schema_ok={ok} {why}")
        if not ok:
            print("FAILED:ADV-0005-probe2 artifact schema")
            return 1
        if E.CATALOG_SENTINEL not in text:
            print("FAILED:ADV-0005-probe2 sentinel-absent")
            return 1
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:ADV-0005-probe2 self-declared {doc.get('state')}")
            return 1
        if doc.get("unblind", {}).get("vote_counting") is not False:
            print("FAILED:ADV-0005-probe2 vote-counting-not-false")
            return 1
        live_ids = {d["id"] for d in unb["disagreements"]}
        art_ids = {d["id"] for d in (doc.get("unblind") or {}).get("disagreements") or []}
        if live_ids != art_ids:
            print(f"FAILED:ADV-0005-probe2 disagreement mismatch live={live_ids} art={art_ids}")
            return 1
        by_id = {
            t["id"]: t.get("verdict")
            for t in (doc.get("targets") or [])
            if isinstance(t, dict)
        }
        if by_id.get("TIEBREAK-IS-SETTLING-NOT-VOTE") != "CONFIRMED":
            print("FAILED:ADV-0005-probe2 tiebreak target not CONFIRMED")
            return 1
        if by_id.get("NAMED-REGISTRY-P0-P1-REDERIVATION") != "NOT-CHECKED":
            print("FAILED:ADV-0005-probe2 named-registry target must be NOT-CHECKED")
            return 1

    if not payload["ok"]:
        print("FAILED:ADV-0005-probe2 unblind/tiebreak failed")
        return 1
    print(
        "SUCCESS:ADV-0005-probe2 disagreements tie-broken by named settling "
        f"experiment (n={unb['disagreement_count']}); vote counting banned"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
