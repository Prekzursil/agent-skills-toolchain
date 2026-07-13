"""Tests for probes/qm.py — the Jaguar QM interaction-energy job probe."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from probes.qm import (  # noqa: E402
    JaguarQmProbe,
    QmJob,
    QmReading,
    _parse_float,
)

_P = JaguarQmProbe()


def _job(reading: QmReading, name: str) -> QmJob:
    return next(job for job in reading.jobs if job.name == name)


class TestJobStates:
    def test_done_exit_zero(self):
        r = _P.parse_jobs(["DONE_cluster_exit_0"])
        job = _job(r, "cluster")
        assert job.state == "done"
        assert job.exit_code == 0
        assert job.scf_failed is False

    def test_scf_failure_exit_three(self):
        r = _P.parse_jobs(["DONE_ligand_exit_3"])
        job = _job(r, "ligand")
        assert job.state == "failed"
        assert job.exit_code == 3
        assert job.scf_failed is True

    def test_non_scf_failure_other_exit(self):
        r = _P.parse_jobs(["DONE_ligand_exit_1"])
        job = _job(r, "ligand")
        assert job.state == "failed"
        assert job.scf_failed is False  # failed, but not the SCF code

    def test_running_with_scf_iteration_and_drms(self):
        r = _P.parse_jobs(["RUNNING cluster", "etot 12 -848.123 0.0009 0.00041"])
        job = _job(r, "cluster")
        assert job.state == "running"
        assert job.iteration == 12
        assert job.drms == 0.00041

    def test_running_marker_without_etot(self):
        r = _P.parse_jobs(["RUNNING pocket"])
        job = _job(r, "pocket")
        assert job.state == "running"
        assert job.iteration is None
        assert job.drms is None

    def test_running_underscore_marker_form(self):
        r = _P.parse_jobs(["RUNNING_ligand", "etot 3 -55.1 0.2 0.02"])
        job = _job(r, "ligand")
        assert job.state == "running"
        assert job.iteration == 3

    def test_done_marker_wins_over_running(self):
        # A job that streamed SCF lines then finished is terminal, not running.
        r = _P.parse_jobs(
            ["RUNNING cluster", "etot 9 -8.0 0.1 0.01", "DONE_cluster_exit_0"]
        )
        assert _job(r, "cluster").state == "done"

    def test_shared_pocket_name_matches_pocket_role(self):
        r = _P.parse_jobs(["DONE_shared_pocket_exit_0"])
        assert _job(r, "shared_pocket").state == "done"
        # The pocket role is satisfied by the shared_pocket job — no phantom
        # pending "pocket" placeholder is seeded.
        assert not any(j.name == "pocket" for j in r.jobs)

    def test_etot_before_any_running_marker_is_ignored(self):
        # No RUNNING context yet ⇒ the SCF line cannot be attributed to a job.
        r = _P.parse_jobs(["etot 5 -1.0 0.1 0.01"])
        assert r.discovered is False
        assert all(job.state == "pending" for job in r.jobs)


class TestPendingRolesAndReadiness:
    def test_unseen_roles_are_pending(self):
        r = _P.parse_jobs(["DONE_cluster_exit_0"])
        assert _job(r, "cluster").state == "done"
        assert _job(r, "ligand").state == "pending"
        assert _job(r, "pocket").state == "pending"

    def test_all_three_done_is_ready(self):
        r = _P.parse_jobs(
            [
                "DONE_cluster_exit_0",
                "DONE_ligand_exit_0",
                "DONE_pocket_exit_0",
            ]
        )
        assert r.interaction_ready is True
        assert r.done_count == 3

    def test_two_done_one_running_not_ready(self):
        r = _P.parse_jobs(
            ["DONE_cluster_exit_0", "DONE_ligand_exit_0", "RUNNING pocket"]
        )
        assert r.interaction_ready is False
        assert r.done_count == 2

    def test_failed_role_is_not_ready(self):
        r = _P.parse_jobs(
            [
                "DONE_cluster_exit_0",
                "DONE_ligand_exit_0",
                "DONE_pocket_exit_3",
            ]
        )
        assert r.interaction_ready is False  # a failed pocket does not count

    def test_running_property_none_when_no_running_job(self):
        r = _P.parse_jobs(["DONE_cluster_exit_0"])
        assert r.running is None

    def test_running_property_returns_the_running_job(self):
        r = _P.parse_jobs(["RUNNING cluster", "etot 4 -8 0.1 0.01"])
        assert r.running is not None
        assert r.running.name == "cluster"


class TestToReading:
    def test_no_signal_is_unknown_early(self):
        # BLIND-aware: nothing discovered ⇒ honest unknown frontier, no fake %.
        reading = _P.parse(["initialising jaguar harness"])
        assert reading.done is None
        assert reading.total is None
        assert reading.fraction() is None
        assert reading.phase == "qm"
        assert reading.terminal is False

    def test_ready_maps_to_terminal_and_full_fraction(self):
        reading = _P.parse(
            [
                "DONE_cluster_exit_0",
                "DONE_ligand_exit_0",
                "DONE_pocket_exit_0",
            ]
        )
        assert reading.done == 3.0
        assert reading.total == 3.0
        assert reading.fraction() == 1.0
        assert reading.terminal is True
        assert "interaction-energy ready" in reading.detail

    def test_running_with_iteration_shows_scf_phase_and_drms(self):
        reading = _P.parse(["RUNNING cluster", "etot 12 -848.1 0.0009 0.00041"])
        assert reading.phase == "cluster scf 12"
        assert reading.gpu.startswith("drms")
        assert reading.done == 0.0
        assert reading.total == 3.0

    def test_running_with_iteration_but_no_drms_has_empty_gpu(self):
        reading = _P.parse(["RUNNING cluster", "etot 12"])
        assert reading.phase == "cluster scf 12"
        assert reading.gpu == ""  # short etot line: iter known, drms unknown

    def test_running_without_iteration_shows_running_phase(self):
        reading = _P.parse(["RUNNING cluster"])
        assert reading.phase == "cluster running"
        assert reading.gpu == ""

    def test_discovered_but_no_running_uses_qm_phase(self):
        reading = _P.parse(["DONE_cluster_exit_0"])
        assert reading.phase == "qm"
        assert reading.done == 1.0
        assert reading.terminal is False


class TestParseFloat:
    def test_none_token(self):
        assert _parse_float(None) is None

    def test_valid_token(self):
        assert _parse_float("0.0004") == 0.0004

    def test_garbage_token(self):
        assert _parse_float("not-a-number") is None

    def test_garbage_drms_field_yields_none(self):
        r = _P.parse_jobs(["RUNNING cluster", "etot 7 -8.0 0.1 ----"])
        job = _job(r, "cluster")
        assert job.iteration == 7
        assert job.drms is None


class TestToDict:
    def test_job_to_dict(self):
        r = _P.parse_jobs(["DONE_ligand_exit_3"])
        d = _job(r, "ligand").to_dict()
        assert d["state"] == "failed"
        assert d["exit_code"] == 3
        assert d["scf_failed"] is True

    def test_reading_to_dict(self):
        r = _P.parse_jobs(["DONE_cluster_exit_0", "RUNNING ligand"])
        d = r.to_dict()
        assert d["done_count"] == 1
        assert d["total"] == 3
        assert d["interaction_ready"] is False
        assert isinstance(d["jobs"], list)
        assert len(d["jobs"]) == 3


class TestRegistryIntegration:
    def test_resolves_and_parses_through_registry(self):
        from probes.registry import get_probe

        probe = get_probe("jaguar-qm")
        assert probe.name == "jaguar-qm"
        reading = probe.parse(["DONE_cluster_exit_0"])
        assert reading.done == 1.0
