#!/usr/bin/env python3
"""Probe 2: known-answer quiz plus production vote-weight acceptance."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import quiz as Q  # noqa: E402
import weights_gate as W  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0099-hallucinated-expertise-in-selection.json"
UID = "ADV-0099"


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0099-probe2 {msg}")
    return 1


def main() -> int:
    cal = Q.run_calibration()
    weights = W.run_weight_paths(cal)
    ctl = cal["control"]
    slim = {
        "probe": "probe2-known-answer-calibration",
        "unit_id": UID,
        "discriminating": cal["discriminating"],
        "flat_accuracy": cal["flat_accuracy"],
        "separation_crypto": cal["separation_crypto"],
        "baseline_lay_crypto_accuracy": cal["baseline_lay_crypto_accuracy"],
        "genuine_crypto_acc_crypto": ctl["genuine_crypto_acc_crypto"],
        "genuine_crypto_acc_unicode": ctl["genuine_crypto_acc_unicode"],
        "claimed_crypto_acc_crypto": ctl["claimed_crypto_acc_crypto"],
        "claimed_crypto_acc_unicode": ctl["claimed_crypto_acc_unicode"],
        "naive_authority": cal["naive_authority_for_crypto_task"],
        "gated_authority": cal["gated_authority_for_crypto_task"],
        "unverifiable_claim_accepted_as_weight": weights["unverifiable_claim_accepted_as_weight"],
        "quiz_refuses_premium": weights["quiz_refuses_premium"],
        "genuine_premium_kept": weights["genuine_premium_kept"],
        "production_ignores_expertise_field": weights["production_ignores_expertise_field"],
        "naive_effective": weights["naive"]["effective"],
        "gated_effective": weights["gated"]["effective"],
        "pass": cal["pass"] and weights["pass"],
    }
    print(json.dumps(slim, indent=2, sort_keys=True))
    if cal["flat_accuracy"]:
        return fail("question set is not discriminating (flat accuracy)")
    if not cal["discriminating"]:
        return fail("domain-separation control failed")
    if not cal["hallucinated_gets_naive_premium"]:
        return fail("naive path did not grant expert weight to claimed-crypto")
    if not cal["hallucinated_refused_gated"]:
        return fail("gated path did not refuse claimed-crypto premium")
    if not cal["genuine_keeps_gated"]:
        return fail("gated path dropped genuine-crypto premium")
    if not weights["pass"]:
        return fail("production resolve_weights did not accept/refuse as measured")
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        rec = doc.get("probe2") or {}
        if rec.get("discriminating") is not True:
            return fail("artifact probe2.discriminating is not true")
        if rec.get("unverifiable_claim_accepted_as_weight") is not True:
            return fail("artifact missing production weight acceptance")
        if abs(float(rec.get("separation_crypto")) - cal["separation_crypto"]) > 1e-9:
            return fail("artifact separation_crypto drift")
    print("SUCCESS:ADV-0099-probe2 known-answer calibration and vote-weight")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
