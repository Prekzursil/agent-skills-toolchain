#!/usr/bin/env python3
"""IMP-0418 oracle tests. Runnable as a script (write_receipts) and via pytest."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from completion_predicate import judge  # noqa: E402
from fanin_sites import SITE_IDS, canonical_verdict_bytes, check_unit  # noqa: E402
from predicate_oracle import (  # noqa: E402
    MIN_BORDERLINE,
    build_corpus,
    run_oracle,
    run_planted_divergence,
)


def test_exit_zero_alone_is_incomplete() -> None:
    out = judge({"state": "RUNNING", "exit_code": 0})
    assert out["verdict"] == "INCOMPLETE"
    assert out["complete"] is False
    assert out["exit_code_consulted"] is False
    assert "C01" in out["failing"]


def test_corpus_size_and_borderline_floor() -> None:
    result = run_oracle()
    assert result["corpus_size"] == 200
    assert result["call_site_count"] == 7
    assert result["borderline_count"] >= MIN_BORDERLINE
    assert result["oracle_too_easy"] is False
    assert result["complete_count"] + result["incomplete_count"] == 200


def test_seven_sites_agree() -> None:
    result = run_oracle()
    assert result["agree"] is True
    assert result["matrix"]["any_disagreement"] is False
    assert result["matrix"]["pair_disagreement_sum"] == 0
    assert len(result["call_sites"]) == 7
    assert list(result["call_sites"]) == list(SITE_IDS)


def test_planted_lax_threshold_fires() -> None:
    planted = run_planted_divergence()
    assert planted["baseline_agree"] is True
    assert planted["baseline_disagreements"] == 0
    assert planted["planted_any_disagreement"] is True
    assert planted["expected_diverging_count"] >= 1
    assert planted["fired"] is True


def test_site_bytes_are_byte_identical_on_gold() -> None:
    gold = [art for art in build_corpus() if judge(art)["complete"] is True]
    assert gold, "corpus has no COMPLETE artifacts"
    for art in gold:
        blobs = [canonical_verdict_bytes(check_unit(site, art)) for site in SITE_IDS]
        assert len(set(blobs)) == 1, art.get("id")


def _run() -> int:
    tests = [
        test_exit_zero_alone_is_incomplete,
        test_corpus_size_and_borderline_floor,
        test_seven_sites_agree,
        test_planted_lax_threshold_fires,
        test_site_bytes_are_byte_identical_on_gold,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - script runner prints the test name
            print(f"FAIL {fn.__name__} {type(exc).__name__}: {exc}")
            failed += 1
            continue
        print(f"PASS {fn.__name__}")
    if failed:
        print(f"FAILED:test_predicate_oracle {len(tests) - failed}/{len(tests)}")
        return 1
    print(f"SUCCESS:test_predicate_oracle {len(tests)}/{len(tests)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
