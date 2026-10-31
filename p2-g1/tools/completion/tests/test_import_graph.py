#!/usr/bin/env python3
"""Live tests: every fan-in site imports the shared reducer judge.

Runnable standalone (``python3 -B tools/completion/tests/test_import_graph.py``)
and importable by the IMP-0417 probes, which call each ``test_*`` directly.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))

from completion import reducer  # noqa: E402
from completion.census import census_dir, import_graph_site  # noqa: E402
from completion.reducer import Observation, judge  # noqa: E402
from completion.sites import SITE_FILES, SITE_IDS, load_all  # noqa: E402


def _complete_observation(artifact: Path) -> Observation:
    """An observation that satisfies all eleven reducer conditions."""
    return Observation(
        site="test",
        exit_code=0,
        state="SUCCESS",
        artifact_path=str(artifact),
        repo_root=str(REPO),
        min_bytes=8,
        sentinel="SENTINEL:TEST",
        schema_ok=True,
        evidence_anchor_count=2,
        tests_passed=True,
        negative_controls_ok=True,
        reviewer_verdict="PASS",
        open_p0_p1=0,
        registered=True,
        downstream_read_ok=True,
    )


def test_seven_sites_import_shared_judge() -> None:
    modules = load_all()
    shared = reducer.judge
    for site_id in SITE_IDS:
        mod = modules[site_id]
        assert mod.judge is shared, f"{site_id} judge is not the shared object"
        graph = import_graph_site(REPO / SITE_FILES[site_id])
        assert graph["ok"], f"{site_id} import graph unparsable"
        assert graph["imported_judge"], f"{site_id} did not import shared judge"
        assert graph["calls_judge"], f"{site_id} never calls judge"


def test_live_sites_have_zero_independent_checks() -> None:
    sites_dir = REPO / "tools" / "completion" / "sites"
    hits = census_dir(sites_dir, root=REPO, detector="ast")
    assert hits == [], f"live sites retain local predicates: {hits}"


def test_exit_zero_alone_is_incomplete() -> None:
    verdict = judge(Observation(site="test", exit_code=0))
    assert verdict.verdict == "INCOMPLETE", "exit-zero alone judged COMPLETE"
    assert verdict.failing_condition_ids, "no failing conditions recorded"


def test_digest_without_file_is_incomplete() -> None:
    with tempfile.TemporaryDirectory(prefix="imp0417-") as raw:
        obs = _complete_observation(Path(raw) / "never-written.json")
        verdict = judge(obs)
    assert verdict.verdict == "INCOMPLETE", "missing artifact judged COMPLETE"
    assert 1 in (verdict.failing_condition_ids or []), "artifact-exists did not fail"
    assert 2 in (verdict.failing_condition_ids or []), "min-bytes did not fail"


def test_complete_requires_stat_and_all_flags() -> None:
    with tempfile.TemporaryDirectory(prefix="imp0417-") as raw:
        artifact = Path(raw) / "receipt.json"
        artifact.write_text('{"sentinel": "SENTINEL:TEST"}\n', encoding="utf-8")
        good = _complete_observation(artifact)
        assert judge(good).verdict == "COMPLETE", "fully-satisfied observation refused"

        for broken_field, broken_value in (
            ("state", "FAILED"),
            ("schema_ok", False),
            ("tests_passed", False),
            ("negative_controls_ok", False),
            ("reviewer_verdict", "FAIL"),
            ("open_p0_p1", 1),
            ("registered", False),
            ("downstream_read_ok", False),
            ("sentinel", "SENTINEL:ABSENT"),
            ("min_bytes", 10**9),
        ):
            obs = _complete_observation(artifact)
            setattr(obs, broken_field, broken_value)
            verdict = judge(obs)
            assert verdict.verdict == "INCOMPLETE", f"{broken_field} drop still COMPLETE"


TESTS = (
    test_seven_sites_import_shared_judge,
    test_live_sites_have_zero_independent_checks,
    test_exit_zero_alone_is_incomplete,
    test_digest_without_file_is_incomplete,
    test_complete_requires_stat_and_all_flags,
)


def main() -> int:
    for fn in TESTS:
        fn()
        print(f"ok {fn.__name__}")
    print(f"SUCCESS:test_import_graph {len(TESTS)} tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
