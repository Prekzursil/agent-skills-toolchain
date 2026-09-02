#!/usr/bin/env python3
"""Probe 1: quota adherence vs known ground-truth ratio, and contradiction survival.

Two signals:
  (a) workflow selected-citation mix, independently recounted from
      final_report.md BEGIN_SELECTED tokens joined to the seeded corpus.
  (b) contradiction tokens present in notes.json that also appear in
      final_report.md BEGIN_CONTRADICTIONS. Notes do not count as survival.
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
from tools.bench.deep_research import run_research  # noqa: E402

EPS = 1e-9


def _quota_ok(measured: dict, config: dict, gt: dict) -> tuple[bool, str]:
    ret = measured["returned_proportion"]
    fav_q = float(config["favourable_quota"])
    unfav_q = float(config["unfavourable_quota"])
    if not measured["markers_present"]:
        return False, "markers-absent"
    if abs(ret["support"] - fav_q) > EPS:
        return False, f"support-mix {ret['support']} != quota {fav_q}"
    if abs(ret["contradict"] - unfav_q) > EPS:
        return False, f"contradict-mix {ret['contradict']} != quota {unfav_q}"
    if abs(gt["support_ratio"] - fav_q) > EPS:
        return False, f"ground-truth support {gt['support_ratio']} != {fav_q}"
    if abs(gt["contradict_ratio"] - unfav_q) > EPS:
        return False, f"ground-truth contradict {gt['contradict_ratio']} != {unfav_q}"
    if ret["polar_n"] != int(config["report_slot_budget"]):
        return False, f"polar_n {ret['polar_n']} != budget"
    if len(ret["contradict_tokens"]) != 3:
        return False, "expected 3 unfavourable citations"
    if len(ret["support_tokens"]) != 7:
        return False, "expected 7 favourable citations"
    return True, "quota-matches-ground-truth-and-config"


def _survival_ok(measured: dict) -> tuple[bool, str]:
    notes_c = measured["notes_contradict_tokens"]
    if len(notes_c) < 4:
        return False, f"notes missing planted contradictions: {notes_c}"
    if measured["contradiction_survival_rate"] != 1.0:
        return False, (
            f"survival {measured['contradiction_survival_rate']} "
            f"notes={notes_c} appendix={measured['appendix_tokens']}"
        )
    if not measured["notes_is_not_final"]:
        return False, "notes copied as final report"
    missing = [t for t in notes_c if t not in set(measured["survived_tokens"])]
    if missing:
        return False, f"dropped from final appendix: {missing}"
    return True, "all-notes-contradictions-in-final-appendix"


def main() -> int:
    C.materialize()
    config = C.load_config()
    quota_corpus = C.load_case("quota")
    survival_corpus = C.load_case("survival")
    gt_quota_declared = quota_corpus.get("ground_truth") or {}

    with tempfile.TemporaryDirectory(prefix="tst-0319-p1-") as tmp:
        tmp_path = Path(tmp)
        qdir = tmp_path / "quota"
        vdir = tmp_path / "survival"
        run_research(quota_corpus, config, out_dir=qdir)
        run_research(survival_corpus, config, out_dir=vdir)
        q_m = M.measure_run(qdir, quota_corpus)
        v_m = M.measure_run(vdir, survival_corpus)

    gt_quota = q_m["ground_truth"]
    quota_ok, quota_why = _quota_ok(q_m, config, gt_quota)
    surv_ok, surv_why = _survival_ok(v_m)
    declared_matches_recount = (
        int(gt_quota_declared.get("support") or -1) == gt_quota["support"]
        and int(gt_quota_declared.get("contradict") or -1) == gt_quota["contradict"]
    )
    ok = quota_ok and surv_ok and declared_matches_recount and q_m["notes_is_not_final"]

    report = {
        "probe": "probe1-quota-and-survival",
        "unit_id": "TST-0319",
        "pass": ok,
        "configured_quota": {
            "favourable": config["favourable_quota"],
            "unfavourable": config["unfavourable_quota"],
            "report_slot_budget": config["report_slot_budget"],
        },
        "quota_corpus": {
            "id": quota_corpus["id"],
            "ok": quota_ok,
            "why": quota_why,
            "ground_truth": gt_quota,
            "returned_proportion": q_m["returned_proportion"],
            "contradiction_survival_rate": q_m["contradiction_survival_rate"],
            "verdict": q_m["verdict"],
            "declared_matches_recount": declared_matches_recount,
        },
        "survival_corpus": {
            "id": survival_corpus["id"],
            "ok": surv_ok,
            "why": surv_why,
            "ground_truth": v_m["ground_truth"],
            "returned_proportion": v_m["returned_proportion"],
            "contradiction_survival_rate": v_m["contradiction_survival_rate"],
            "notes_contradict_tokens": v_m["notes_contradict_tokens"],
            "survived_tokens": v_m["survived_tokens"],
            "verdict": v_m["verdict"],
        },
        "signals": [
            "selected-citation-tokens-joined-to-seeded-corpus",
            "notes-to-final-appendix-token-survival",
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:TST-0319-probe1 quota or survival")
        return 1
    print(
        "SUCCESS:TST-0319-probe1 quota matches 70/30 ground truth; "
        "contradictions survive into the final appendix"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
