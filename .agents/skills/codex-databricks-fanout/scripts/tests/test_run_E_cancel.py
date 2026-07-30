"""Interrupting the local poller must not leave the remote Databricks job running.

Observed 2026-07-26: a 3-unit coverage fan-out was stopped locally at ~5m. All artifacts had
landed at 3m04s, but the submitted run stayed RUNNING and was still billing an r5d.2xlarge
~15 minutes later, found only by a manual sweep. At the configured 48-way concurrency that is
a real cost exposure, so the wait loop owns cancellation on interrupt.

This file also pins the rest of the reconciled driver's behaviour, because each item below was
present in exactly ONE of the two long-diverged copies of run_E.py and so had no test at all on
the other side:
  * `cancel_run` + cancel-on-interrupt (above)
  * SUBMIT-FAILED as a verdict distinct from FAILED, printed loudly
  * timeout_s=None by default (no wall-clock cap) with an explicit cap still honoured
  * `_verdict` selecting between the TWO live gate impls (engine.verify / harness.poll.classify)
  * run_coverage_fanout injecting NO write token (R1)
"""

from __future__ import annotations

import inspect
import json
import shutil
from pathlib import Path

import pytest

from harness.contract import LANE_SCHEMAS, Unit, floor_for
from harness.lanes import run_E

# submit_and_gate writes batch.json/payload.json beside the module, under scripts/e2e/_E_<name>.
E2E_ROOT = Path(run_E.__file__).resolve().parents[2] / "e2e"


def _coverage_unit(uid="u0"):
    """Distinct from test_engine_verify._unit, which is a module-private smoke-lane fixture."""
    return Unit(
        id=uid, lane="coverage", prompt="p", artifact=f"/dbfs/tmp/E-x/results/{uid}.md"
    )


@pytest.fixture
def probe_name():
    """Name a submit_and_gate run and delete the scratch dir it creates in the checkout.

    Without this every test that reaches submit_and_gate leaves an untracked
    scripts/e2e/_E_<name>/payload.json behind; `no-runtime-junk` only polices TRACKED junk, but a
    suite that dirties `git status` still hides real changes from the next reader.
    """
    names: list[str] = []

    def _name(n):
        names.append(n)
        return n

    yield _name
    for n in names:
        shutil.rmtree(E2E_ROOT / f"_E_{n}", ignore_errors=True)


class _StubResult:
    def __init__(self, ok):
        self.ok = ok


class _StubVerify:
    """Stands in for engine.verify, which is DBX-side only and absent from the skill mirror."""

    def __init__(self, ok=True):
        self._ok = ok
        self.seen: list[tuple[str, object]] = []

    def and_gate(self, unit, artifact_path):
        self.seen.append((unit.id, artifact_path))
        return _StubResult(self._ok)


def _stub_submit(monkeypatch, run_id=99117):
    """Neutralise batch build + payload upload; keep the real wait/gate loop under test."""
    monkeypatch.setattr(run_E.build_batch, "write_batch", lambda b, p: p)
    monkeypatch.setattr(run_E.build_batch, "build_batch", lambda u, n: {})
    monkeypatch.setattr(run_E.submit, "build_payload", lambda *a, **k: {})
    monkeypatch.setattr(run_E.submit, "submit", lambda pf, rc: run_id)


def _terminal_run_cmd(state="TERMINATED"):
    def run_cmd(argv):
        if argv[:3] == ["databricks", "jobs", "get-run"]:
            return 0, json.dumps({"state": {"life_cycle_state": state}}), ""
        return 0, "", ""

    return run_cmd


def _harvest_writes_artifact(monkeypatch, body="x"):
    def _h(dbfs_result, dest, units, run_cmd):
        dest.mkdir(parents=True, exist_ok=True)
        for u in units:
            (dest / Path(u.artifact).name).write_text(body, encoding="utf-8")
        return {u.id: ("harvested", len(body)) for u in units}

    monkeypatch.setattr(run_E.harvest, "harvest", _h)


def test_cancel_run_issues_cancel_and_reports_success():
    seen = []

    def run_cmd(argv):
        seen.append(argv)
        return 0, "", ""

    assert run_E.cancel_run(4242, run_cmd) is True
    assert seen == [
        ["databricks", "jobs", "cancel-run", "4242", "--profile", run_E.RAIL["profile"]]
    ]


def test_cancel_run_reports_failure_without_raising():
    """A failed cancel must not mask the original interrupt."""
    assert run_E.cancel_run(7, lambda argv: (1, "", "boom")) is False


def test_cancel_run_swallows_a_raising_run_cmd():
    """`databricks` missing / timing out raises; that must not replace the interrupt either."""

    def boom(argv):
        raise OSError("no databricks CLI")

    assert run_E.cancel_run(7, boom) is False


def test_interrupt_cancels_the_submitted_run(monkeypatch, probe_name):
    """KeyboardInterrupt during the wait loop cancels the run, then re-raises."""
    cancelled = []

    _stub_submit(monkeypatch)
    monkeypatch.setattr(
        run_E, "cancel_run", lambda rid, rc: cancelled.append(rid) or True
    )

    def run_cmd(argv):
        if argv[:3] == ["databricks", "jobs", "get-run"]:
            raise KeyboardInterrupt  # interrupt arrives mid-poll
        return 0, "", ""

    with pytest.raises(KeyboardInterrupt):
        run_E.submit_and_gate(
            [_coverage_unit()], probe_name("interrupt-probe"), run_cmd=run_cmd
        )

    assert cancelled == [99117], "the submitted run must be cancelled before re-raising"


def test_interrupt_reports_a_failed_cancel(monkeypatch, capsys, probe_name):
    """When the cancel itself fails the operator is told to do it by hand."""
    _stub_submit(monkeypatch)
    monkeypatch.setattr(run_E, "cancel_run", lambda rid, rc: False)

    def run_cmd(argv):
        if argv[:3] == ["databricks", "jobs", "get-run"]:
            raise SystemExit(1)  # SystemExit is caught alongside KeyboardInterrupt
        return 0, "", ""

    with pytest.raises(SystemExit):
        run_E.submit_and_gate(
            [_coverage_unit()], probe_name("interrupt-probe-2"), run_cmd=run_cmd
        )
    assert "cancel it manually" in capsys.readouterr().out


def test_submit_rejection_is_loud_and_not_a_unit_failure(
    monkeypatch, capsys, probe_name
):
    """A rejected cluster used to read as N silently FAILED units, so a 6-shard chain flew past
    as 0/48 with no clue why. The verdict must be distinguishable and the reason printed."""
    _stub_submit(monkeypatch, run_id=None)
    units = [_coverage_unit("u0"), _coverage_unit("u1")]

    verdicts = run_E.submit_and_gate(
        units, probe_name("reject-probe"), run_cmd=lambda argv: (0, "", "")
    )

    assert verdicts == {"u0": ("SUBMIT-FAILED", None), "u1": ("SUBMIT-FAILED", None)}
    out = capsys.readouterr().out
    assert "SUBMIT REJECTED" in out and "NOT a unit failure" in out


def test_default_is_no_wall_clock_cap():
    """A hard cap produced a FALSE-NEGATIVE TIMEOUT on a run whose artifacts were complete
    (2026-07-24 e2e dogfood), so None -- poll until the job is terminal -- is the default."""
    assert (
        inspect.signature(run_E.submit_and_gate).parameters["timeout_s"].default is None
    )


def test_explicit_timeout_still_caps(monkeypatch, probe_name):
    """The cap is opt-in, not removed."""
    _stub_submit(monkeypatch)
    verdicts = run_E.submit_and_gate(
        [_coverage_unit()],
        probe_name("cap-probe"),
        run_cmd=_terminal_run_cmd("RUNNING"),
        timeout_s=0,
    )
    assert verdicts == {"u0": ("TIMEOUT", None)}


def test_engine_import_is_guarded_not_required():
    """The skill mirror ships harness/ + lanes/ without engine/, so the driver must import in
    both trees; `_verdict` picks the gate at call time."""
    assert run_E.verify is None or hasattr(run_E.verify, "and_gate")


@pytest.mark.parametrize("ok,expected", [(True, "DONE"), (False, "FAILED")])
def test_verdict_uses_engine_verify_when_available(monkeypatch, ok, expected):
    stub = _StubVerify(ok)
    monkeypatch.setattr(run_E, "verify", stub)
    unit = _coverage_unit()

    assert run_E._verdict("TERMINATED", unit, "/tmp/u0.md") == expected
    assert stub.seen == [("u0", "/tmp/u0.md")], (
        "the harvested path is forwarded as a str"
    )


def test_verdict_falls_back_to_poll_classify(monkeypatch):
    """harness.poll.classify is NOT retired: it is the only impl with an UNKNOWN verdict, and it
    is what runs wherever engine/ is absent."""
    monkeypatch.setattr(run_E, "verify", None)
    seen = []

    def classify(state, unit, artifact):
        seen.append((state, unit.id, artifact))
        return "UNKNOWN"

    monkeypatch.setattr(run_E.poll, "classify", classify)

    assert run_E._verdict("TERMINATED", _coverage_unit(), "/tmp/u0.md") == "UNKNOWN"
    assert seen == [("TERMINATED", "u0", "/tmp/u0.md")]


@pytest.mark.parametrize("shortfall,expected", [(0, "DONE"), (600, "FAILED")])
def test_verdict_str_path_satisfies_the_real_fallback_gate(
    monkeypatch, tmp_path, shortfall, expected
):
    """fetch() hands the gate a `str`, not a Path -- pin that against the REAL poll.classify.

    Both gates funnel into harness.contract.and_gate_artifact, which does `Path(artifact)`, so a
    str is legal -- this asserts exactly that, against the real gate, so a str-hostile gate would
    be a red test rather than a silent all-FAILED fan-out. It does NOT pin the forwarding itself;
    that is test_terminal_state_gates_harvested_artifacts, which compares against `str(...)` and
    goes red if fetch() reverts to returning a Path. The fixture is built from the contract's OWN
    constants so a change to the lane schema or the byte floor cannot make this test lie.
    """
    monkeypatch.setattr(run_E, "verify", None)
    unit = _coverage_unit()
    fields = "\n".join(f"{f}: measured" for f in sorted(LANE_SCHEMAS[unit.lane]))
    sentinel = f"\nUNIT-COMPLETE: {unit.id}\n"
    body = fields + "\n" + "filler line\n" * 200
    artifact = tmp_path / f"{unit.id}.md"
    artifact.write_text(
        (body + sentinel)[: max(0, floor_for(unit.lane) - shortfall)] + sentinel,
        encoding="utf-8",
    )

    assert run_E._verdict("TERMINATED", unit, str(artifact)) == expected


def test_terminal_state_gates_harvested_artifacts(monkeypatch, capsys, probe_name):
    """End-to-end through the real wait loop: terminal state -> harvest -> gate -> DONE."""
    _stub_submit(monkeypatch)
    _harvest_writes_artifact(monkeypatch)
    stub = _StubVerify(True)
    monkeypatch.setattr(run_E, "verify", stub)

    name = probe_name("gate-probe")
    verdicts = run_E.submit_and_gate(
        [_coverage_unit()], name, run_cmd=_terminal_run_cmd()
    )

    verdict, path = verdicts["u0"]
    assert verdict == "DONE"
    assert Path(path) == E2E_ROOT / f"_E_{name}" / "results" / "u0.md"
    assert stub.seen == [("u0", str(E2E_ROOT / f"_E_{name}" / "results" / "u0.md"))]
    assert "1/1 DONE" in capsys.readouterr().out


def test_failed_gate_retries_the_harvest_three_times(monkeypatch, probe_name):
    """DBFS is eventually consistent, so a non-DONE batch is re-harvested twice more before the
    verdict stands. Assert the retry count so the grace loop cannot silently become 1 pass."""
    _stub_submit(monkeypatch)
    _harvest_writes_artifact(monkeypatch)
    stub = _StubVerify(False)
    monkeypatch.setattr(run_E, "verify", stub)
    monkeypatch.setattr(run_E.time, "sleep", lambda s: None)

    verdicts = run_E.submit_and_gate(
        [_coverage_unit()], probe_name("regate-probe"), run_cmd=_terminal_run_cmd()
    )

    assert verdicts["u0"][0] == "FAILED"
    assert len(stub.seen) == 3


def test_unharvested_artifact_gates_as_no_artifact(monkeypatch, probe_name):
    """fetch() returns None when harvest did not land the file; the gate must see the None."""
    _stub_submit(monkeypatch)
    monkeypatch.setattr(
        run_E.harvest,
        "harvest",
        lambda dbfs, dest, units, rc: {u.id: ("missing", 0) for u in units},
    )
    stub = _StubVerify(False)
    monkeypatch.setattr(run_E, "verify", stub)
    monkeypatch.setattr(run_E.time, "sleep", lambda s: None)

    run_E.submit_and_gate(
        [_coverage_unit()], probe_name("nofetch-probe"), run_cmd=_terminal_run_cmd()
    )
    assert stub.seen == [("u0", None)] * 3


def test_coverage_fanout_injects_no_write_token(monkeypatch):
    """R1: the node gets NO write token and only commits agent/ branches locally. The pre-merge
    driver passed extra_env={"GITHUB_TOKEN": "{{secrets/.../github_token}}"} plus timeout_s=5400
    here; both are deliberately gone (a long-lived write token in a 48-way job cluster is the
    exposure R1 removes, and the cap is the false-negative TIMEOUT)."""
    seen = {}

    def fake(units, name, run_cmd=None, extra_env=None, timeout_s=None, poll_s=30):
        seen.update(name=name, extra_env=extra_env, timeout_s=timeout_s, n=len(units))
        return {}

    monkeypatch.setattr(
        run_E.coverage, "coverage_units", lambda repo, gaps: [_coverage_unit("g0")]
    )
    monkeypatch.setattr(run_E, "submit_and_gate", fake)

    run_E.run_coverage_fanout("env-inspector", ["a.py"])

    assert seen == {
        "name": "coverage-env-inspector",
        "extra_env": None,
        "timeout_s": None,
        "n": 1,
    }


def test_coverage_fanout_with_no_gaps_submits_nothing(monkeypatch, capsys):
    monkeypatch.setattr(run_E.coverage, "coverage_units", lambda repo, gaps: [])
    monkeypatch.setattr(
        run_E, "submit_and_gate", lambda *a, **k: pytest.fail("must not submit")
    )

    assert run_E.run_coverage_fanout("env-inspector", []) == {}
    assert "no gaps" in capsys.readouterr().out


def test_step_1_and_2_pass_no_wall_clock_cap(monkeypatch):
    """node_preflight/runnability used to hard-code timeout_s=1800/2400. Those caps are gone;
    assert it, so re-adding one is a red test rather than a silent false-negative TIMEOUT."""
    calls = []

    def fake(units, name, run_cmd=None, extra_env=None, timeout_s=None, poll_s=30):
        calls.append((name, timeout_s, extra_env))
        return {
            units[0].id: ("FAILED", None)
        }  # early-return; the gate is not under test here

    monkeypatch.setattr(run_E, "submit_and_gate", fake)
    monkeypatch.setattr(
        run_E.preflight_units, "node_preflight_unit", lambda: _coverage_unit("pf")
    )
    monkeypatch.setattr(
        run_E.preflight_units,
        "runnability_unit",
        lambda repo, url: _coverage_unit("rn"),
    )

    ok, ver, msg = run_E.node_preflight()
    assert (ok, ver) == (False, "unknown") and "not DONE" in msg

    assert run_E.runnability("env-inspector", "https://example.invalid/r") == (
        False,
        [],
        "",
    )
    assert calls == [
        ("preflight-node", None, None),
        ("preflight-run-env-inspector", None, None),
    ]
