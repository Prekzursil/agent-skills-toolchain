"""Dedup / minimise / seed-reproducibility tests for tools.fuzz_triage."""
from __future__ import annotations

from fuzz_triage.engine import (
    SEED_RECIPES,
    committed_corpus,
    crash_from_outcome,
    execute_tracked,
    materialise,
    minimise,
    payload_fingerprint,
    run_campaign,
    sha256_bytes,
    triage_crashes,
)


def test_two_inputs_with_one_root_cause_dedup_to_one_entry() -> None:
    left = execute_tracked(b"hello\xffworld-pad")
    right = execute_tracked(b"\xff" + b"other-padding-xx")
    assert left.fingerprint == right.fingerprint
    live = triage_crashes([crash_from_outcome(left), crash_from_outcome(right)])
    assert len(live) == 1 and live[0].count == 2 and live[0].exception_func == "_crash_a"
    mutant = triage_crashes(
        [crash_from_outcome(left), crash_from_outcome(right)],
        fingerprint=payload_fingerprint,
        do_minimise=False,
    )
    assert len(mutant) == 2


def test_crashing_input_is_minimised() -> None:
    padded = b"AAAA\xffBBBBCCCC"
    fp = execute_tracked(padded).fingerprint
    small = minimise(padded, fp)
    assert small == b"\xff"
    assert execute_tracked(small).fingerprint == fp
    assert execute_tracked(b"").ok


def test_corpus_seeds_are_reproducible_from_the_receipt() -> None:
    records = committed_corpus()
    assert len(records) == len(SEED_RECIPES) == 5
    for rec in records:
        data = materialise(rec["recipe"])
        assert rec["bytes_hex"] == data.hex()
        assert rec["sha256"] == sha256_bytes(data)
        assert b"\xff" not in data and b"\xfe" not in data
    first = run_campaign(campaign_seed=117000, budget=120)
    second = run_campaign(campaign_seed=117000, budget=120)
    assert [e.fingerprint for e in first.triage] == [e.fingerprint for e in second.triage]
    assert first.crash_count == second.crash_count >= 2
