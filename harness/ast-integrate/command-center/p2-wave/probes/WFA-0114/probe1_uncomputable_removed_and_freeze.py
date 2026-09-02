#!/usr/bin/env python3
"""Probe 1: uncomputable components are removed (not zero-filled); freeze gate.

Both-states:
  * recovery computable on source_a (first-attempt failures exist) and retained
  * recovery uncomputable on fusion_outperforms (all first attempts pass) and removed
  * zero-filling the removed slot changes the composite — proving we did not
    keep it at weight zero
  * usability removed on fusion_no_attempts (empty attempted set)
  * certify refuses before freeze and after a post-hoc formula mutation;
    certify proceeds after freeze
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
    print(f"FAILED:WFA-0114-probe1 {msg}")
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
    if doc.get("unit_id") != "WFA-0114":
        return fail(f"unit_id {doc.get('unit_id')}")

    fx = json.loads(FIX.read_text(encoding="utf-8"))
    matched = list(fx["matched_intersection"])
    corpus = list(fx["corpus_case_ids"])
    arms = fx["arms"]
    spec = R.HeadToHeadRubric()

    src = spec.score_arm(arms["source_a"], matched)
    rec_src = next(c for c in src["named"] if c["id"] == "recovery")
    if rec_src.get("status") != "retained":
        return fail(f"source_a recovery not retained {rec_src}")
    if abs(float(rec_src["value"]) - 0.5) > 1e-12:
        return fail(f"source_a recovery {rec_src['value']} want=0.5")

    # Independent recount of source_a correctness from raw fields (not the composite blob).
    n_pass = 0
    for cid in matched:
        run = (arms["source_a"].get("runs") or {}).get(cid) or {}
        if run.get("oracle") == "pass":
            n_pass += 1
    want_corr = n_pass / len(matched)
    corr = next(c for c in src["named"] if c["id"] == "correctness")
    if abs(float(corr["value"]) - want_corr) > 1e-12:
        return fail(f"correctness {corr['value']} independent={want_corr}")

    fus = spec.score_arm(arms["fusion_outperforms"], matched)
    rec_fus = next(c for c in fus["named"] if c["id"] == "recovery")
    if rec_fus.get("status") != "removed":
        return fail(f"fusion_outperforms recovery not removed {rec_fus}")
    if fus["arm_composite"]["value"] is None:
        return fail("fusion arm composite missing")
    if abs(fus["arm_composite"]["value"] - fus["zero_filled_named_composite"]) < 1e-12:
        return fail(
            "removed recovery produced the same composite as zero-fill; "
            "that is weighting down, not removal"
        )
    if abs(fus["arm_composite"]["value"] - 1.0) > 1e-12:
        return fail(f"fusion arm composite {fus['arm_composite']['value']} want=1.0")
    if abs(fus["zero_filled_named_composite"] - 0.75) > 1e-12:
        return fail(
            f"zero-fill {fus['zero_filled_named_composite']} want=0.75 "
            "(1+1+0+1)/4"
        )

    none = spec.score_arm(arms["fusion_no_attempts"], matched)
    use = next(c for c in none["named"] if c["id"] == "usability")
    if use.get("status") != "removed":
        return fail(f"no-attempts usability not removed {use}")
    cov = next(c for c in none["named"] if c["id"] == "coverage")
    if cov.get("status") != "retained" or abs(float(cov["value"]) - 0.0) > 1e-12:
        return fail(f"no-attempts coverage should be retained 0 {cov}")

    unfrozen = R.HeadToHeadRubric()
    d0 = unfrozen.decide(
        arms["fusion_outperforms"], [arms["source_a"], arms["source_b"]], matched, corpus
    )
    if d0.get("decision") != "REFUSED":
        return fail(f"unfrozen decide {d0.get('decision')}")

    frozen = R.HeadToHeadRubric()
    frozen.freeze("2026-08-24T00:00:00Z")
    d1 = frozen.decide(
        arms["fusion_outperforms"], [arms["source_a"], arms["source_b"]], matched, corpus
    )
    if d1.get("decision") != "OUTPERFORMS":
        return fail(f"frozen decide {d1.get('decision')} {d1.get('reason')}")

    frozen.mutate_formula("usability", "always 1 after seeing the leaderboard")
    d2 = frozen.decide(
        arms["fusion_outperforms"], [arms["source_a"], arms["source_b"]], matched, corpus
    )
    if d2.get("decision") != "REFUSED":
        return fail(f"post-hoc decide {d2.get('decision')}")

    freeze = doc.get("freeze") or {}
    if freeze.get("frozen") is not True:
        return fail("artifact freeze.frozen is not true")
    if freeze.get("freeze_hash") != freeze.get("live_digest"):
        return fail("artifact freeze hash drifted from live digest")
    if (freeze.get("unfrozen_certify") or {}).get("decision") != "REFUSED":
        return fail("artifact missing unfrozen refuse")
    if (freeze.get("post_hoc_mutate_certify") or {}).get("decision") != "REFUSED":
        return fail("artifact missing post-hoc refuse")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if tests.get("WFA0114-UNCOMPUTABLE-REMOVED", {}).get("result") != "PASS":
        return fail("artifact test UNCOMPUTABLE not PASS")
    if tests.get("WFA0114-RUBRIC-FROZEN", {}).get("result") != "PASS":
        return fail("artifact test FROZEN not PASS")

    payload = {
        "pass": True,
        "probe": "probe1-uncomputable-removed-and-freeze",
        "unit_id": "WFA-0114",
        "source_a_recovery": rec_src["value"],
        "fusion_recovery_status": rec_fus["status"],
        "arm_composite": fus["arm_composite"]["value"],
        "zero_filled": fus["zero_filled_named_composite"],
        "unfrozen": d0["decision"],
        "frozen": d1["decision"],
        "post_hoc": d2["decision"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:WFA-0114-probe1 recovery removed not zero-filled; "
        "usability removed when unattempted; freeze gate refuses then accepts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
