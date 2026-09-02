#!/usr/bin/env python3
"""Probe 2: recompute 2x2 from planted_items, disjoint-set stability, overclaim guards."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from calibrate import run_calibration  # noqa: E402
from pipeline import confusion, false_pass_rate  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0133.json"


def reject_percentages_only(doc: dict) -> bool:
    """True if the artifact would fail an overclaim check (percentages without raw counts)."""
    cm = doc.get("confusion_matrix")
    if not isinstance(cm, dict):
        return True
    for k in ("true_positive", "false_positive", "false_negative", "true_negative"):
        if not isinstance(cm.get(k), int):
            return True
    fpr = doc.get("false_pass_rate")
    if not isinstance(fpr, dict) or "numerator" not in fpr or "denominator" not in fpr:
        return True
    return False


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0133-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0133" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0133-probe2 sentinel absent")
        return 1

    rows = list(doc.get("planted_items") or [])
    if len(rows) < 8:
        print(f"FAILED:CNF-0133-probe2 planted_items={len(rows)} want>=8")
        return 1
    recomputed = confusion(rows)
    published = doc.get("confusion_matrix") or {}
    print("recomputed", json.dumps(recomputed), "published", json.dumps(published))
    if recomputed != {k: published[k] for k in recomputed}:
        print("FAILED:CNF-0133-probe2 arithmetic mismatch")
        return 1

    if reject_percentages_only(doc):
        print("FAILED:CNF-0133-probe2 raw counts missing")
        return 1
    mutant = copy.deepcopy(doc)
    mutant["confusion_matrix"] = {"false_pass_percent": 12.5}
    if not reject_percentages_only(mutant):
        print("FAILED:CNF-0133-probe2 percentages-only mutant was accepted")
        return 1
    print("overclaim_guard_ok=True percentages-only mutant rejected")

    fpr = false_pass_rate(recomputed)
    pub_fpr = doc.get("false_pass_rate") or {}
    if pub_fpr.get("numerator") != fpr["numerator"] or pub_fpr.get("denominator") != fpr["denominator"]:
        print("FAILED:CNF-0133-probe2 false_pass_rate mismatch", pub_fpr, fpr)
        return 1
    if fpr["denominator"] < 1:
        print("FAILED:CNF-0133-probe2 no planted-false items")
        return 1
    if fpr["numerator"] > 0 and pub_fpr.get("value") == 0:
        print("FAILED:CNF-0133-probe2 overclaim: fp>0 but value=0")
        return 1

    cal = run_calibration()
    live_b = cal["runs"]["set_b"]["false_pass_rate"]
    art_b = (doc.get("per_set") or {}).get("set_b", {}).get("false_pass_rate") or {}
    print("set_b live", json.dumps(live_b), "artifact", json.dumps(art_b))
    if live_b.get("numerator") != art_b.get("numerator") or live_b.get("denominator") != art_b.get("denominator"):
        print("FAILED:CNF-0133-probe2 set_b stability mismatch")
        return 1
    art_a = (doc.get("per_set") or {}).get("set_a", {}).get("false_pass_rate") or {}
    if art_a.get("value") != art_b.get("value"):
        print("FAILED:CNF-0133-probe2 set_a vs set_b rate not stable", art_a, art_b)
        return 1

    ids_a = {r["claim_id"] for r in rows if r.get("set_id") == "set_a"}
    ids_b = {r["claim_id"] for r in rows if r.get("set_id") == "set_b"}
    if not ids_a or not ids_b or ids_a & ids_b:
        print("FAILED:CNF-0133-probe2 planted sets not disjoint", len(ids_a), len(ids_b), len(ids_a & ids_b))
        return 1

    for rec in (doc.get("confirmation_records_set_a") or []) + (doc.get("confirmation_records_set_b") or []):
        sp = (rec.get("source_probe") or {}).get("fingerprint")
        vp = (rec.get("verifier_probe") or {}).get("fingerprint")
        if not sp or not vp or sp == vp:
            print("FAILED:CNF-0133-probe2 source/verifier fingerprint", rec.get("claim_id"))
            return 1
        if rec.get("verdict") in {"CONFIRMED", "REFUTED"} and not sp:
            print("FAILED:CNF-0133-probe2 unsourced terminal verdict")
            return 1

    surviving_fp = [
        r
        for r in rows
        if r.get("oracle_label") == "false"
        and r.get("operator_class") == "surviving"
        and r.get("confirmer_verdict") == "CONFIRMED"
    ]
    killed_tn = [
        r
        for r in rows
        if r.get("oracle_label") == "false"
        and r.get("operator_class") == "killed"
        and r.get("confirmer_verdict") == "REFUTED"
    ]
    print(f"surviving_false_pass={len(surviving_fp)} killed_true_negative={len(killed_tn)}")
    if not surviving_fp:
        print("FAILED:CNF-0133-probe2 expected surviving-mutant false-pass")
        return 1
    if not killed_tn:
        print("FAILED:CNF-0133-probe2 expected killed-mutant REFUTED")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        print("FAILED:CNF-0133-probe2 reviewer not independent")
        return 1
    if not (rev.get("planting_blind") and rev.get("arithmetic")):
        print("FAILED:CNF-0133-probe2 two reviewers not recorded")
        return 1

    import inspect

    from pipeline import confirm_claim  # noqa: E402

    sig = str(inspect.signature(confirm_claim))
    if "label" in sig.lower() or "oracle" in sig.lower() or "plant" in sig.lower():
        print("FAILED:CNF-0133-probe2 confirm_claim signature takes a plant/oracle argument")
        return 1
    src = (HERE / "pipeline.py").read_text(encoding="utf-8")
    if "labels.json" in src:
        print("FAILED:CNF-0133-probe2 confirmer module opens a labels file")
        return 1

    print("SUCCESS:CNF-0133-probe2 arithmetic stability overclaim fingerprints")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
