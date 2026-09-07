"""CNF-0015 both-states tests: detector FAILS on pre-fix, PASSES on post-fix."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROBE = Path(__file__).resolve().parent
REPO = PROBE.parents[3]  # CNF-0015 -> probes -> p2-wave -> command-center -> repo
sys.path.insert(0, str(PROBE))
sys.path.insert(0, str(REPO / "tools" / "detector-self-test"))

import detector_self_test as dst  # noqa: E402
import option_id_collision as oic  # noqa: E402

PRE = PROBE / "fixtures" / "pre-fix"
POST = PROBE / "fixtures" / "post-fix"


def test_pre_fix_shared_id_count_is_31() -> None:
    report = oic.measure_dir(PRE)
    assert report.shared_id_count == 31
    assert report.collision_live is True
    assert len(report.family_m_ids) == 33
    assert report.mech_token_count == 0
    assert report.decision_present_tense_collision is True


def test_post_fix_shared_id_count_is_0() -> None:
    report = oic.measure_dir(POST)
    assert report.shared_id_count == 0
    assert report.collision_live is False
    assert report.doc13_bare_m_ids == frozenset()


def test_detector_opposite_results_on_both_states() -> None:
    """Catalog tests_required: FAIL on pre-fix backup, PASS on today's doc 13."""
    assert oic.collision_is_live(PRE) is True
    assert oic.collision_is_live(POST) is False


def test_both_states_fixture_rejects_silent_and_accepts_real_detector() -> None:
    obs = dst.assert_both_states(
        oic.collision_is_live,
        broken=PRE,
        good=POST,
        name="CNF-0015-option-id-collision",
    )
    assert obs.fired_on_broken is True
    assert obs.fired_on_good is False


def test_silent_detector_is_rejected_by_fixture() -> None:
    with pytest.raises(dst.BothStatesError):
        dst.assert_both_states(
            lambda _p: False, broken=PRE, good=POST, name="silent"
        )
