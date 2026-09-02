#!/usr/bin/env python3
"""Tests for the health-check runner and probe registry (IMP-0043).

Stdlib-only with its own ``__main__``; the catalog-named test is
``test_blocked_probe_prevents_healthy_aggregate``.  Every aggregate rule is
exercised in both states: a healthy fixture IS healthy, and each way of being
not-healthy (blocked, failed, thrown, unrun, empty) is shown to flip it.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
import health_check as hc  # noqa: E402
import health_probes as hp  # noqa: E402


def _healthy_report(force: dict[str, str] | None = None) -> hc.HealthReport:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        hp.plant_healthy_tree(root)
        return hc.run_all(hc.default_registry(), hc.HealthContext(root=root, force_state=force or {}))


def test_healthy_aggregate() -> None:
    report = _healthy_report()
    assert report.healthy and report.aggregate == "HEALTHY", report.to_dict()
    assert [row.probe_id for row in report.probes] == list(hp.REQUIRED_PROBE_IDS)
    assert report.reason == "all-registered-probes-ran-and-succeeded"
    assert report.blocked_ids == [] and report.failed_ids == [] and report.missing_unrun == []


def test_blocked_probe_prevents_healthy_aggregate() -> None:
    report = _healthy_report({"hooks_loaded": "BLOCKED"})
    assert not report.healthy and report.aggregate == "NOT-HEALTHY"
    assert "hooks_loaded" in report.blocked_ids
    assert report.reason.startswith("blocked:hooks_loaded")
    forced = next(row for row in report.probes if row.probe_id == "hooks_loaded")
    assert forced.state == "BLOCKED" and forced.evidence.get("forced") is True


def test_forced_failed_is_failed_not_blocked() -> None:
    report = _healthy_report({"cache_valid": "FAILED"})
    assert not report.healthy
    assert report.failed_ids == ["cache_valid"] and report.blocked_ids == []


class _Thrower:
    probe_id = "thrower"

    def run(self, ctx: hc.HealthContext) -> hc.ProbeResult:
        raise RuntimeError("boom")


class _BadReturn:
    probe_id = "bad_return"

    def run(self, ctx: hc.HealthContext) -> object:
        return {"state": "SUCCESS"}


def test_throwing_probe_is_failed_never_healthy() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        hp.plant_healthy_tree(root)
        registry = hc.default_registry()
        registry.register(_Thrower())
        report = hc.run_all(registry, hc.HealthContext(root=root))
    row = next(r for r in report.probes if r.probe_id == "thrower")
    assert row.state == "FAILED" and row.evidence.get("uncaught") is True
    assert not report.healthy and "thrower" in report.failed_ids


def test_non_probe_result_return_is_failed() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        hp.plant_healthy_tree(root)
        registry = hc.Registry()
        registry.register(_BadReturn())
        report = hc.run_all(registry, hc.HealthContext(root=root))
    assert report.probes[0].state == "FAILED" and not report.healthy


def test_unrun_registered_probe_is_not_pass() -> None:
    report = _healthy_report()
    registry = hc.default_registry()
    partial = [row for row in report.probes if row.probe_id != "mcp_reachable"]
    unrun = hc.aggregate(registry, partial)
    assert not unrun.healthy and unrun.missing_unrun == ["mcp_reachable"]
    assert unrun.reason == "unrun:mcp_reachable"
    assert hc.aggregate(registry, []).healthy is False


def test_registry_refuses_duplicate_ids_and_runless_probes() -> None:
    registry = hc.default_registry()
    try:
        registry.register(hp.default_probes()[0])
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate probe id accepted")
    try:
        registry.register(object())
    except TypeError:
        pass
    else:
        raise AssertionError("probe without run() accepted")


def test_every_default_probe_carries_a_both_states_control_that_discriminates() -> None:
    registry = hc.default_registry()
    rows = registry.require_both_states()
    assert [r["probe_id"] for r in rows] == list(hp.REQUIRED_PROBE_IDS)
    assert all(r["unit_id"] == "IMP-0044" and r["present"] for r in rows)
    executed = hc.run_both_states(registry)
    bad = [r for r in executed if not r["ok"]]
    assert not bad, bad
    assert all(r["observed_good"] == "SUCCESS" and r["observed_broken"] == "FAILED" for r in executed)


def test_broken_tree_fails_every_probe_and_isolated_break_fails_only_one() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        hp.plant_broken_tree(root)
        report = hc.run_all(hc.default_registry(), hc.HealthContext(root=root))
        assert not report.healthy
        assert set(report.failed_ids) == set(hp.REQUIRED_PROBE_IDS), report.failed_ids
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        hp.plant_broken_tree(root, only="deploy_in_sync")
        report = hc.run_all(hc.default_registry(), hc.HealthContext(root=root))
        assert report.failed_ids == ["deploy_in_sync"], report.failed_ids
        row = report.probes[-1]
        assert row.evidence["reason"] == "sha256-differs"


def test_missing_root_fails_every_probe_with_evidence() -> None:
    with tempfile.TemporaryDirectory() as td:
        report = hc.run_all(hc.default_registry(), hc.HealthContext(root=Path(td) / "absent"))
    assert not report.healthy and len(report.failed_ids) == len(hp.REQUIRED_PROBE_IDS)
    assert all(row.evidence.get("exists") is False or row.evidence.get("live_exists") is False for row in report.probes)


def test_report_validates_against_schema_and_bad_documents_do_not() -> None:
    document = _healthy_report().to_dict()
    assert hc.validate_report(document) == []
    assert hc.validate_report({"healthy": True, "aggregate": "HEALTHY"}), "missing probes accepted"
    assert hc.validate_report({**document, "aggregate": "FINE"}), "unknown aggregate accepted"
    broken = {**document, "probes": [{"probe_id": "x", "state": "MAYBE"}]}
    assert hc.validate_report(broken), "non-terminal state accepted"


def test_cli_fixture_both_states_and_force() -> None:
    cli = [sys.executable, "-B", str(PLUGIN / "health_check.py")]
    ok = subprocess.run([*cli, "--fixture", "healthy", "--both-states"], capture_output=True, text=True, timeout=120)
    assert ok.returncode == 0 and "SUCCESS:health-check HEALTHY" in ok.stdout, ok.stdout[-800:] + ok.stderr[-800:]
    forced = subprocess.run(
        [*cli, "--fixture", "healthy", "--force", "hooks_loaded=BLOCKED"], capture_output=True, text=True, timeout=120
    )
    assert forced.returncode == 1 and "reason=blocked:hooks_loaded" in forced.stdout, forced.stdout[-800:]
    broken = subprocess.run([*cli, "--fixture", "broken"], capture_output=True, text=True, timeout=120)
    assert broken.returncode == 1 and "FAILED:health-check NOT-HEALTHY" in broken.stdout


TESTS = [
    test_healthy_aggregate,
    test_blocked_probe_prevents_healthy_aggregate,
    test_forced_failed_is_failed_not_blocked,
    test_throwing_probe_is_failed_never_healthy,
    test_non_probe_result_return_is_failed,
    test_unrun_registered_probe_is_not_pass,
    test_registry_refuses_duplicate_ids_and_runless_probes,
    test_every_default_probe_carries_a_both_states_control_that_discriminates,
    test_broken_tree_fails_every_probe_and_isolated_break_fails_only_one,
    test_missing_root_fails_every_probe_with_evidence,
    test_report_validates_against_schema_and_bad_documents_do_not,
    test_cli_fixture_both_states_and_force,
]


def main() -> int:
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"ok   {test.__name__}")
        except Exception:  # noqa: BLE001 - report every failure, then the verdict
            failed += 1
            print(f"FAIL {test.__name__}")
            traceback.print_exc()
    if failed:
        print(f"FAILED:IMP-0043-tests {failed}/{len(TESTS)} checks failed")
        return 1
    print(f"SUCCESS:IMP-0043-tests {len(TESTS)}/{len(TESTS)} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
