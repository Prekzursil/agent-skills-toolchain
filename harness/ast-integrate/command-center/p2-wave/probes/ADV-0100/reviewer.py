#!/usr/bin/env python3
"""Independent reviewer: re-derive exclusions from fixtures, not the report.

Catalog asks for a cross-vendor Codex (openai) refuter. That vendor did
not sign. This reviewer re-walks lineage and re-computes author-field
sets by importing the instrument, then checks the live artifact's
target verdicts against those sets.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import coi_filter as C  # noqa: E402
import fixtures as F  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0100-conflict-of-interest-self-review.json"


def rederive() -> dict:
    F.dump_json()
    control = C.analyse(F.detector_control_known_present(), mode="author-field")
    direct = C.analyse(F.planted_direct(), mode="author-field")
    undeclared = C.analyse(F.undeclared_direct(), mode="author-field")
    trans_field = C.analyse(F.planted_transitive(), mode="author-field")
    trans_lin = C.analyse(F.planted_transitive(), mode="lineage")
    clean_field = C.analyse(F.clean_independent(), mode="author-field")
    clean_lin = C.analyse(F.clean_independent(), mode="lineage")
    empty = C.analyse(F.empty_roster(), mode="author-field")
    prod_direct = C.analyse(F.planted_direct(), mode="production")
    prod_trans = C.analyse(F.planted_transitive(), mode="production")

    control_ok = (
        control["status"] == "FIRE"
        and C.KNOWN_SELF_AUTHOR in control["excluded"]
        and control["independent_kept"] is True
    )
    direct_ok = (
        direct["status"] == "FIRE"
        and C.KNOWN_SELF_AUTHOR in direct["excluded"]
        and C.INDEPENDENT_ID in direct["kept"]
    )
    undeclared_ok = (
        undeclared["status"] == "FIRE"
        and C.KNOWN_SELF_AUTHOR in undeclared["excluded"]
    )
    # author-field must MISS the original writer; lineage must catch them
    field_misses_lineage = (
        C.KNOWN_LINEAGE_AUTHOR not in trans_field["excluded"]
        and C.KNOWN_LINEAGE_AUTHOR in trans_field["eligible"]
        and trans_field["status"] == "SILENT"
    )
    lineage_catches = (
        trans_lin["status"] == "FIRE"
        and C.KNOWN_LINEAGE_AUTHOR in trans_lin["excluded"]
        and trans_lin["independent_kept"] is True
    )
    clean_ok = (
        clean_field["status"] == "SILENT"
        and clean_lin["status"] == "SILENT"
        and clean_field["independent_kept"] is True
        and C.INDEPENDENT_ID in clean_field["kept"]
        and "BOB-REVIEWER" in clean_field["kept"]
    )
    empty_ok = empty["status"] == "NOT-CHECKED" and empty["fired"] is False

    fires = 0
    if clean_field["fired"] or clean_lin["fired"]:
        fires = 1
    rate = fires / 1.0

    return {
        "control_ok": control_ok,
        "direct_ok": direct_ok,
        "undeclared_ok": undeclared_ok,
        "field_misses_lineage": field_misses_lineage,
        "lineage_catches": lineage_catches,
        "clean_ok": clean_ok,
        "empty_ok": empty_ok,
        "independent_not_excluded": (
            clean_ok and direct["independent_kept"] and trans_lin["independent_kept"]
        ),
        "false_positive_rate": {"fires": fires, "clean_fixtures_total": 1, "rate": rate},
        "production_direct_leaked": list(prod_direct.get("leaked_self_review") or []),
        "production_trans_leaked": list(prod_trans.get("leaked_self_review") or []),
        "production_why": prod_direct.get("production_why"),
        "passed": all(
            [
                control_ok,
                direct_ok,
                undeclared_ok,
                field_misses_lineage,
                lineage_catches,
                clean_ok,
                empty_ok,
            ]
        ),
        "added_failure_mode": {
            "id": "FM-PSEUDONYM-ALIAS",
            "title": "Same person, two seat ids",
            "author_missed": True,
            "description": (
                "Author-field and lineage walks match string ids. A participant "
                "that reviews under a second identifier is not joined. That is a "
                "different detector (identity resolution), recorded as missed."
            ),
        },
    }


def review() -> dict:
    rerun = rederive()
    artifact_ok = True
    artifact_note = "artifact-absent"
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        targets = {t.get("id"): t.get("verdict") for t in (doc.get("targets") or [])}
        direct_verdict = targets.get("T-DIRECT-SELF-REVIEW")
        trans_verdict = targets.get("T-TRANSITIVE-LINEAGE-SELF-REVIEW")
        want_direct = "CONFIRMED" if rerun["production_direct_leaked"] else "REFUTED"
        want_trans = "CONFIRMED" if rerun["production_trans_leaked"] else "REFUTED"
        artifact_ok = direct_verdict == want_direct and trans_verdict == want_trans
        artifact_note = (
            f"direct={direct_verdict} want={want_direct} "
            f"trans={trans_verdict} want={want_trans}"
        )
        if doc.get("reviewer", {}).get("vendor_constraint_met") is True:
            artifact_ok = False
            artifact_note += " overclaim-vendor"
    return {
        "reviewer_id": "ADV-0100-mechanical-lineage-reviewer",
        "verdict": "PASS" if rerun["passed"] and artifact_ok else "FAIL",
        "independent": True,
        "scope_not_agreement": True,
        "vendor_constraint_met": False,
        "both_states_rerun": True,
        "artifact_ok": artifact_ok,
        "artifact_note": artifact_note,
        "added_failure_mode": rerun["added_failure_mode"],
        "rerun": rerun,
    }


if __name__ == "__main__":
    rec = review()
    print(json.dumps({k: v for k, v in rec.items() if k != "rerun"}, sort_keys=True))
    print(f"passed={rec['rerun']['passed']} artifact_ok={rec['artifact_ok']}")
    raise SystemExit(0 if rec["verdict"] == "PASS" else 1)
