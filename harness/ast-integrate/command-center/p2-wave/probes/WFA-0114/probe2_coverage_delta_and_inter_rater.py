#!/usr/bin/env python3
"""Probe 2: independent reviewer — coverage-delta complementarity + inter-rater.

Both-states:
  * fusion_complement does not beat sources on the matched composite but unique
    coverage delta >= floor → MATERIALLY_COMPLEMENTARY; unique cases are listed
    and are not in the head-to-head correctness numerator
  * fusion_padded has more stages, identical matched oracles, zero unique delta
    → REJECT (stage count is not a qualifying signal)
  * fusion_outperforms still OUTPERFORMS
  * high-agreement human ratings are retained; low-agreement ratings are removed
    rather than kept with a caveat or a smaller weight
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import rubric as R  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0114-headtohead-scoring-rubric.json"
FIX = HERE / "fixtures" / "recorded_runs.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0114-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:WFA-0114" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    fx = json.loads(FIX.read_text(encoding="utf-8"))
    matched = list(fx["matched_intersection"])
    corpus = list(fx["corpus_case_ids"])
    arms = fx["arms"]
    sources = [arms["source_a"], arms["source_b"]]
    spec = R.HeadToHeadRubric()
    spec.freeze("2026-08-24T00:00:00Z")

    # Independent unique-solve set: fusion pass and no source pass, over corpus.
    def solved(arm: dict) -> set[str]:
        out = set()
        for cid in corpus:
            run = (arm.get("runs") or {}).get(cid) or {}
            if run.get("oracle") == "pass":
                out.add(cid)
        return out

    unique = sorted(
        solved(arms["fusion_complement"])
        - solved(arms["source_a"])
        - solved(arms["source_b"])
    )
    if unique != ["c07", "c08", "c09"]:
        return fail(f"unique {unique} want=['c07','c08','c09']")
    delta = len(unique) / len(corpus)
    if abs(delta - 0.3) > 1e-12:
        return fail(f"delta {delta} want=0.3")

    # Unique cases must not inflate matched correctness (only c01 of 6 matched).
    n_pass_matched = 0
    for cid in matched:
        run = (arms["fusion_complement"].get("runs") or {}).get(cid) or {}
        if run.get("oracle") == "pass":
            n_pass_matched += 1
    if n_pass_matched != 1:
        return fail(f"matched passes {n_pass_matched} want=1 (unique not folded)")
    scored = spec.score_arm(arms["fusion_complement"], matched)
    corr = next(c for c in scored["named"] if c["id"] == "correctness")
    if abs(float(corr["value"]) - (1 / 6)) > 1e-12:
        return fail(f"complement correctness {corr['value']} want=1/6")

    d_comp = spec.decide(arms["fusion_complement"], sources, matched, corpus)
    if d_comp.get("decision") != "MATERIALLY_COMPLEMENTARY":
        return fail(f"complement decision {d_comp.get('decision')} {d_comp.get('reason')}")
    if d_comp.get("outperforms") is True:
        return fail("complement fusion must not be classified as outperforms")
    fus_val = (d_comp.get("fusion") or {}).get("comparison_composite", {}).get("value")
    best = d_comp.get("best_source_comparison_composite")
    if fus_val is None or best is None or fus_val >= best:
        return fail(f"complement composite {fus_val} should be < best source {best}")
    if d_comp["complement"]["unique_case_ids"] != unique:
        return fail("engine unique set drifted from independent recount")
    if d_comp["complement"].get("folded_into_head_to_head") is not False:
        return fail("complementarity folded into head-to-head")

    d_pad = spec.decide(arms["fusion_padded"], sources, matched, corpus)
    if d_pad.get("decision") != "REJECT":
        return fail(f"padded decision {d_pad.get('decision')}")
    if int(arms["fusion_padded"]["stages"]) <= int(arms["source_a"]["stages"]):
        return fail("padded fixture is not actually larger")
    if d_pad["complement"]["n_unique"] != 0:
        return fail("padded fusion unexpectedly unique")

    d_out = spec.decide(arms["fusion_outperforms"], sources, matched, corpus)
    if d_out.get("decision") != "OUTPERFORMS":
        return fail(f"outperform decision {d_out.get('decision')}")

    high = R.component_human(
        fx["inter_rater"]["high_agreement"]["rater_a"],
        fx["inter_rater"]["high_agreement"]["rater_b"],
    )
    low = R.component_human(
        fx["inter_rater"]["low_agreement"]["rater_a"],
        fx["inter_rater"]["low_agreement"]["rater_b"],
    )
    if high.get("status") != "retained":
        return fail(f"high-agreement human not retained {high}")
    if float(high.get("kappa") or 0) < R.AGREEMENT_FLOOR:
        return fail(f"high kappa {high.get('kappa')}")
    if low.get("status") != "removed":
        return fail(f"low-agreement human not removed {low}")
    if float(low.get("kappa") or 0) >= R.AGREEMENT_FLOOR:
        return fail(f"low kappa {low.get('kappa')} unexpectedly above floor")
    if "weight" in json.dumps(low).lower() and "down" in json.dumps(low).lower():
        pass
    if low.get("value") is not None:
        return fail("removed human component still carries a value (down-weight)")

    # Artifact must publish the same operational rule, not a prose substitute.
    art_comp = (doc.get("comparisons") or {}).get("fusion_complement") or {}
    if art_comp.get("decision") != "MATERIALLY_COMPLEMENTARY":
        return fail("artifact complement decision drifted")
    art_delta = (art_comp.get("complement") or {}).get("delta")
    if art_delta is None or abs(float(art_delta) - 0.3) > 1e-12:
        return fail(f"artifact delta {art_delta}")
    art_pad = (doc.get("comparisons") or {}).get("fusion_padded") or {}
    if art_pad.get("decision") != "REJECT":
        return fail("artifact padded decision drifted")
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if tests.get("WFA0114-COMPLEMENT-DELTA", {}).get("result") != "PASS":
        return fail("artifact complement test not PASS")
    ir = doc.get("inter_rater") or {}
    if (ir.get("low_agreement") or {}).get("status") != "removed":
        return fail("artifact low-agreement not removed")
    if (ir.get("high_agreement") or {}).get("status") != "retained":
        return fail("artifact high-agreement not retained")

    payload = {
        "pass": True,
        "probe": "probe2-coverage-delta-and-inter-rater",
        "unit_id": "WFA-0114",
        "unique": unique,
        "delta": delta,
        "complement_decision": d_comp["decision"],
        "padded_decision": d_pad["decision"],
        "outperform_decision": d_out["decision"],
        "matched_correctness": corr["value"],
        "high_kappa": high.get("kappa"),
        "low_kappa": low.get("kappa"),
        "low_status": low.get("status"),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:WFA-0114-probe2 unique coverage delta is complementary; "
        "padded stages are not; low inter-rater agreement removes the human component"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
