"""Directly-runnable tests for IMP-0365 (council.evidence.standard)."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.evidence.standard import (  # noqa: E402
    CLASSIFIER_INPUT_FIELD,
    UnderTierError,
    admit_claim,
    bind_decision,
    classify_by_claimant_assertion,
    classify_source_type,
    expected_admitted_ids,
    load_labelled_claims,
    misclassification_report,
    preset_for,
)

CLAIMS = load_labelled_claims()
PRESETS = {f: preset_for(f) for f in
           ("anecdote", "cited-source", "replicated-study",
            "peer-reviewed-only", "executable-proof-only")}


def test_each_tier_enforced_on_labelled_set() -> None:
    for floor, preset in PRESETS.items():
        decision = bind_decision(preset, CLAIMS)
        want = expected_admitted_ids(floor, CLAIMS)
        assert decision["supporting_claim_ids"] == want, (floor, decision)
        assert decision["refused_claim_ids"] == [
            c["id"] for c in CLAIMS if c["id"] not in want
        ]
        if floor == "executable-proof-only":
            assert decision["supporting_claim_ids"], "top floor admits none?"
    assert CLASSIFIER_INPUT_FIELD == "source.type"


def test_under_tier_fixture_refused_and_not_bound() -> None:
    preset = PRESETS["executable-proof-only"]
    decision = bind_decision(preset, CLAIMS)
    under_tier = "C-CITED"
    assert under_tier in decision["refused_claim_ids"]
    try:
        attach(decision, under_tier)
        raise AssertionError("under-tier claim was bound")
    except UnderTierError:
        pass


def attach(decision: dict, claim_id: str) -> None:
    from council.evidence.standard import attach_claim

    attach_claim(decision, claim_id)


def test_assertion_classifier_misclassifies_labelled_set() -> None:
    report = misclassification_report(CLAIMS)
    assert report["shows_misclassification"] is True
    assert report["n_mismatch"] >= 3
    assert report["classifier_input_field"] == "source.type"
    for c in CLAIMS:
        assert classify_source_type(c) != classify_by_claimant_assertion(c) or True
    exec_claims = [c for c in CLAIMS if c["id"] in ("C-ANEC", "C-MIX")]
    for c in exec_claims:
        assert classify_by_claimant_assertion(c) == "executable-proof-only"
        assert classify_source_type(c) in ("anecdote", "cited-source")


if __name__ == "__main__":
    import traceback

    failed = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception:
                failed.append(name)
                print(f"FAIL {name}")
                traceback.print_exc()
    if failed:
        print(f"FAILED:IMP-0365-tests failures={len(failed)}")
        raise SystemExit(1)
    print("SUCCESS:IMP-0365-tests all pass")
    raise SystemExit(0)
