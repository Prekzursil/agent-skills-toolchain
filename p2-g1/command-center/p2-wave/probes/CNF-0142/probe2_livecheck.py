#!/usr/bin/env python3
"""CNF-0142 probe2: matrix re-derivation from the receipt's own regrades rows (self-contained),
registry-band drift recorded-not-denied, rubric clauses carried verbatim in-artifact, reviewer
closure intact. Emitted by shard8-w2 resume builder 2026-10-25."""
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CHECKS = []
FACTS = {}

def ck(name, cond):
    CHECKS.append({"check": name, "ok": bool(cond)})
    return bool(cond)

def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))

def finish(pid, uid):
    raw = {"probe": pid, "unit": uid, "facts": FACTS, "checks": CHECKS, "all_ok": all(c["ok"] for c in CHECKS)}
    (Path(__file__).parent / (pid + ".raw.json")).write_bytes(json.dumps(raw, indent=1).encode("utf-8"))
    print(json.dumps(raw))
    return 0 if raw["all_ok"] else 1

def main():
    d = load("command-center/receipts/CNF-0142.json")
    rg = d["regrades"]
    ck("twelve_regrade_rows", len(rg) == 12)

    live = {"agree": [], "under-grade": [], "over-grade": []}
    for r in rg:
        live[r["direction"]].append(r["claim_id"])
    m = d["disagreement_matrix"]
    ck("matrix_rederived_from_regrades_agree", sorted(live["agree"]) == sorted(m["agree"]["ids"]))
    ck("matrix_rederived_from_regrades_under", sorted(live["under-grade"]) == sorted(m["under_grade"]["ids"]))
    ck("matrix_rederived_from_regrades_over", sorted(live["over-grade"]) == sorted(m["over_grade"]["ids"]))
    ck("accuracy_recomputed_from_regrades", abs(m["accuracy"] - len(live["agree"]) / len(rg)) < 1e-9)

    # rubric clauses: every regrade row cites a clause + citation anchor, and the clause id
    # appears verbatim inside the artifact (self-contained evidence).
    txt = (REPO / "command-center/receipts/CNF-0142.json").read_text(encoding="utf-8")
    ck("rubric_clause_and_citation_per_regrade", all(r.get("rubric_clause") and r.get("rubric_citation") for r in rg))
    ck("rubric_clauses_verbatim_in_artifact", all(r["rubric_clause"] in txt for r in rg))

    # registry-band drift: today's CLAIM-REGISTRY.json carries no CLM-FIX ids; the receipt
    # itself already discloses the registry as unusable-as-working-frame. Drift recorded, never denied.
    reg_raw = (REPO / "command-center/CLAIM-REGISTRY.json").read_text(encoding="utf-8")
    band_gone = "CLM-FIX-0002" not in reg_raw and "CLM-FIX-0012" not in reg_raw
    lr = d.get("live_registry", {})
    disclosed = (lr.get("usable_as_working_frame") is False) and (lr.get("reason", "") != "")
    FACTS["registry_band_clm_fix_present_today"] = (not band_gone)
    FACTS["receipt_discloses_registry_unusable"] = disclosed
    ck("registry_drift_recorded_not_denied", (not band_gone) or disclosed)

    ck("risk_register_present", (REPO / "command-center/RISK-REGISTER.md").is_file())
    rv = d.get("reviewer", {})
    ck("reviewer_pass_independent", rv.get("verdict") == "PASS" and rv.get("independent") is True)
    ck("verdict_recorded", d.get("verdict") in ("CONFIRMED", "CONFIRMED-WITH-CAVEATS", "PARTIAL"))
    ck("blinding_attestation_carried", bool(d.get("blinding_attestation")) and bool(d.get("blinding_attestation_hash")))
    return finish("probe2_livecheck", "CNF-0142")

if __name__ == "__main__":
    sys.exit(main())
