#!/usr/bin/env python3
"""Probe 2: forced re-divergence vs second-round theater.

Independent signal is taxonomy category coverage (breadth.py), a different
data field from the detector's Jaccard cluster counts. A second round of
paraphrases must not raise coverage and must not permit reconverge.
Complement ideas in uncovered categories must raise coverage and permit
reconverge.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))

import breadth as B  # noqa: E402
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402
import reviewer as R  # noqa: E402
import schema_validate as SV  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0095-premature-convergence-and-forced-re-divergence.md"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0095-probe2 {msg}")
    return 1


def main() -> int:
    theater = F.theater_second_round()
    complement = F.complement_rediverge()

    t_cov = B.coverage_report(theater)
    c_cov = B.coverage_report(complement)
    t_prog = D.post_freeze_progress(theater)
    c_prog = D.post_freeze_progress(complement)
    t_det = D.detect(theater)
    c_det = D.detect(complement)

    print(
        "theater "
        f"fired_first={t_det['fired']} coverage_delta={t_cov['coverage_delta']} "
        f"breadth_recovered={t_cov['breadth_recovered']} "
        f"reconverge_permitted={t_prog['permitted']} "
        f"new_idea_clusters_in_complement={t_prog.get('new_idea_clusters_in_complement')} "
        f"covered_first={t_cov['covered_at_first_converge']} "
        f"covered_last={t_cov['covered_at_last_converge']}"
    )
    print(
        "complement "
        f"fired_first={c_det['fired']} coverage_delta={c_cov['coverage_delta']} "
        f"breadth_recovered={c_cov['breadth_recovered']} "
        f"reconverge_permitted={c_prog['permitted']} "
        f"new_idea_clusters_in_complement={c_prog.get('new_idea_clusters_in_complement')} "
        f"new_objection_clusters={c_prog.get('new_objection_clusters')} "
        f"covered_first={c_cov['covered_at_first_converge']} "
        f"covered_last={c_cov['covered_at_last_converge']}"
    )

    if not t_det["fired"] or not c_det["fired"]:
        return fail("first-stop pathology must still FIRE on both intervention fixtures")
    if t_cov["coverage_delta"] != 0.0 or t_cov["breadth_recovered"]:
        return fail("second-round theater raised coverage; that is not lost-breadth recovery")
    if t_prog["permitted"]:
        return fail("second-round theater permitted reconverge")
    if not c_cov["breadth_recovered"] or c_cov["coverage_delta"] <= 0:
        return fail("complement intervention did not raise category coverage")
    if not c_prog["permitted"]:
        return fail("complement intervention did not permit reconverge")
    if int(c_prog.get("new_idea_clusters_in_complement") or 0) < 1:
        return fail("complement added no new idea clusters in uncovered categories")

    # Independent field: coverage uses categories, not detector.fired.
    if t_cov["coverage_at_first"] != t_cov["coverage_at_last"]:
        return fail("theater coverage first/last drifted")
    if c_cov["coverage_at_last"] <= c_cov["coverage_at_first"]:
        return fail("complement coverage did not increase")

    rev = R.review()
    print(
        f"reviewer_verdict={rev['verdict']} both_states_rerun={rev['both_states_rerun']} "
        f"independent={rev['independent']}"
    )
    if rev["verdict"] != "PASS" or not rev["both_states_rerun"]:
        return fail("reviewer did not re-run both-states to PASS")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    inter = SV.domain(doc).get("intervention") or {}
    if inter.get("theater_permits_reconverge") is not False:
        return fail("artifact did not record theater as blocked")
    if inter.get("complement_permits_reconverge") is not True:
        return fail("artifact did not record complement as permitted")
    if float(inter.get("theater_coverage_delta", 1)) != 0.0:
        return fail("artifact theater coverage_delta mismatch")
    if not inter.get("complement_breadth_recovered"):
        return fail("artifact complement breadth_recovered mismatch")
    if "SUCCESS:CNL-0095" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    print("SUCCESS:CNL-0095-probe2 re-divergence-vs-theater independent-coverage reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
