#!/usr/bin/env python3
"""Probe 2: suppression control, proof-of-impossibility, drop-disconfirming mutant.

Mechanically different from probe 1: this probe never treats quota mix as
the thing under test. It plants a synthesizer that drops contradictions
from the final report and requires that synthesizer to FAIL survival,
suppression, and impossibility. The honest workflow must PASS the same
fixtures (both-states).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

import corpora as C  # noqa: E402
import measure as M  # noqa: E402
from drop_disconfirming import run_drop_disconfirming  # noqa: E402
from tools.bench.deep_research import (  # noqa: E402
    VERDICT_CONSENSUS,
    VERDICT_CONTRADICTION_DOMINANT,
    VERDICT_IMPOSSIBLE,
    run_research,
)


def _honest_suppression_ok(measured: dict) -> tuple[bool, str]:
    gt = measured["ground_truth"]
    if not gt["contradict_stronger"]:
        return False, "independent strength recount did not find contradict-stronger"
    if abs(gt["support_strength"] - 0.80) > 1e-9:
        return False, f"support strength {gt['support_strength']}"
    if abs(gt["contradict_strength"] - 2.70) > 1e-9:
        return False, f"contradict strength {gt['contradict_strength']}"
    if measured["verdict"] == VERDICT_CONSENSUS:
        return False, "honest reported CONSENSUS over stronger contradictions"
    if measured["verdict"] != VERDICT_CONTRADICTION_DOMINANT:
        return False, f"verdict {measured['verdict']}"
    if measured["contradiction_survival_rate"] != 1.0:
        return False, "honest dropped contradictions while judging dominance"
    return True, "contradiction-dominant-not-consensus"


def _honest_impossibility_ok(measured: dict) -> tuple[bool, str]:
    rec = measured.get("impossibility")
    if not isinstance(rec, dict):
        return False, "impossibility record absent"
    exhausted = rec.get("exhausted_source_classes") or []
    if not exhausted:
        return False, "exhausted source classes empty (not-found masquerading)"
    queries = rec.get("queries_run") or []
    if len(queries) != len(exhausted):
        return False, "query count != exhausted class count"
    if any(int(q.get("hits") or 0) != 0 for q in queries if isinstance(q, dict)):
        return False, "impossibility record has hits"
    if rec.get("kind") != "proof-of-impossibility":
        return False, f"kind {rec.get('kind')}"
    if rec.get("code_path") != "emit_impossibility_record":
        return False, "shared code path with a normal report"
    if rec.get("claim_id") != "CLAIM-GHOST":
        return False, f"claim {rec.get('claim_id')}"
    if not rec.get("falsifier"):
        return False, "falsifier missing"
    if not rec.get("expiry"):
        return False, "expiry missing"
    if measured["verdict"] != VERDICT_IMPOSSIBLE:
        return False, f"verdict {measured['verdict']}"
    if measured["ground_truth"]["polar"] != 0:
        return False, "asked-for claim unexpectedly present"
    return True, "proof-of-impossibility-on-ghost-claim"


def main() -> int:
    C.materialize()
    config = C.load_config()
    suppression = C.load_case("suppression")
    ghost = C.load_case("impossibility")
    survival = C.load_case("survival")
    quota = C.load_case("quota")

    with tempfile.TemporaryDirectory(prefix="tst-0319-p2-") as tmp:
        tmp_path = Path(tmp)
        h_sup = tmp_path / "honest-suppression"
        h_imp = tmp_path / "honest-impossibility"
        d_sup = tmp_path / "drop-suppression"
        d_imp = tmp_path / "drop-impossibility"
        d_surv = tmp_path / "drop-survival"
        d_quota = tmp_path / "drop-quota"

        run_research(suppression, config, out_dir=h_sup)
        run_research(ghost, config, out_dir=h_imp)
        run_drop_disconfirming(suppression, config, out_dir=d_sup)
        run_drop_disconfirming(ghost, config, out_dir=d_imp)
        run_drop_disconfirming(survival, config, out_dir=d_surv)
        run_drop_disconfirming(quota, config, out_dir=d_quota)

        h_sup_m = M.measure_run(h_sup, suppression)
        h_imp_m = M.measure_run(h_imp, ghost)
        d_sup_m = M.measure_run(d_sup, suppression)
        d_imp_m = M.measure_run(d_imp, ghost)
        d_surv_m = M.measure_run(d_surv, survival)
        d_quota_m = M.measure_run(d_quota, quota)

    sup_ok, sup_why = _honest_suppression_ok(h_sup_m)
    imp_ok, imp_why = _honest_impossibility_ok(h_imp_m)

    drop_fails_suppression = d_sup_m["verdict"] == VERDICT_CONSENSUS
    drop_fails_survival = (
        d_surv_m["notes_contradict_tokens"]
        and d_surv_m["contradiction_survival_rate"] == 0.0
        and not d_surv_m["appendix_tokens"]
    )
    drop_fails_quota = d_quota_m["returned_proportion"]["contradict"] == 0.0
    drop_imp_file_absent = d_imp_m.get("impossibility") is None

    fired_on_bad = (
        drop_fails_suppression
        and drop_fails_survival
        and drop_fails_quota
        and drop_imp_file_absent
        and d_imp_m["verdict"] == VERDICT_CONSENSUS
    )
    silent_on_good = sup_ok and imp_ok
    ok = fired_on_bad and silent_on_good

    report = {
        "probe": "probe2-suppression-impossibility-drop-control",
        "unit_id": "TST-0319",
        "pass": ok,
        "fired_on_bad_state": fired_on_bad,
        "silent_on_good_state": silent_on_good,
        "planted_synthesizer": "drop-disconfirming",
        "honest_suppression": {
            "ok": sup_ok,
            "why": sup_why,
            "verdict": h_sup_m["verdict"],
            "ground_truth": h_sup_m["ground_truth"],
            "contradiction_survival_rate": h_sup_m["contradiction_survival_rate"],
            "returned_proportion": h_sup_m["returned_proportion"],
        },
        "honest_impossibility": {
            "ok": imp_ok,
            "why": imp_why,
            "verdict": h_imp_m["verdict"],
            "record": h_imp_m.get("impossibility"),
            "ground_truth": h_imp_m["ground_truth"],
        },
        "drop_suppression": {
            "verdict": d_sup_m["verdict"],
            "fails_contract": drop_fails_suppression,
        },
        "drop_survival": {
            "notes_contradict_tokens": d_surv_m["notes_contradict_tokens"],
            "contradiction_survival_rate": d_surv_m["contradiction_survival_rate"],
            "appendix_tokens": d_surv_m["appendix_tokens"],
            "fails_contract": drop_fails_survival,
        },
        "drop_quota": {
            "returned_proportion": d_quota_m["returned_proportion"],
            "fails_contract": drop_fails_quota,
        },
        "drop_impossibility": {
            "verdict": d_imp_m["verdict"],
            "impossibility": d_imp_m.get("impossibility"),
            "fails_contract": drop_imp_file_absent
            and d_imp_m["verdict"] == VERDICT_CONSENSUS,
        },
        "does_on_reject_state": (
            "FIRES: drop-disconfirming writes contradictions into notes, "
            "omits them from the final appendix, reports CONSENSUS on the "
            "stronger-contradict corpus, and treats a missing claim as CONSENSUS "
            "instead of a proof-of-impossibility record."
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    if not ok:
        print("FAILED:TST-0319-probe2 suppression, impossibility, or drop control")
        return 1
    print(
        "SUCCESS:TST-0319-probe2 stronger contradictions are not consensus; "
        "ghost claim is impossible; drop-disconfirming fails the contract"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
