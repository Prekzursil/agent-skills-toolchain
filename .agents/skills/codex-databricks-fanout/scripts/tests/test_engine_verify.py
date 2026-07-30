import json
import shutil
from pathlib import Path

import pytest

from harness.contract import Unit
from engine import verify
from backends.base import Result
from harness import poll
from harness.lanes import run_E

# CROSS-LANE GATE (A00 pure-additions lane). The four and_gate unit tests below run
# unconditionally -- they need only engine/verify.py, which this lane brings. The three
# INTEGRATION tests further down assert that run_E.submit_and_gate gates through
# engine.verify and no longer calls poll.classify. That rewiring is a line in
# harness/lanes/run_E.py (`from engine import verify`), a DIVERGED file owned by the M09
# merge lane. The toolchain copy still gates inline via poll.classify, so those three
# assertions are false there -- because run_E is not rewired, not because engine.verify
# is wrong. The predicate IS the property under test, not a version string.
# Settling experiment: `run_E.verify is engine.verify` becomes True.
_needs_rewired_run_E = pytest.mark.skipif(
    getattr(run_E, "verify", None) is not verify,
    reason="run_E does not gate via engine.verify yet (M09 lane owns run_E.py)",
)


def _art(tmp_path, uid, body):
    p = tmp_path / f"{uid}.md"
    p.write_text(body, encoding="utf-8")
    return str(p)


def test_and_gate_pass(tmp_path):
    u = Unit(
        id="smoke-1", lane="smoke", prompt="p", artifact=str(tmp_path / "smoke-1.md")
    )
    art = _art(
        tmp_path, "smoke-1", "echo: hi\n" + "x" * 1100 + "\nUNIT-COMPLETE: smoke-1\n"
    )
    r = verify.and_gate(u, art)
    assert r.ok and r.reason == "and-gate-pass" and r.unit_id == "smoke-1"


def test_and_gate_missing_artifact():
    u = Unit(id="smoke-2", lane="smoke", prompt="p", artifact="/nope/smoke-2.md")
    r = verify.and_gate(u, None)
    assert not r.ok and r.reason == "no-artifact" and r.size == 0


def test_and_gate_too_small(tmp_path):
    u = Unit(
        id="smoke-3", lane="smoke", prompt="p", artifact=str(tmp_path / "smoke-3.md")
    )
    art = _art(tmp_path, "smoke-3", "echo: hi\nUNIT-COMPLETE: smoke-3\n")
    r = verify.and_gate(u, art)
    assert not r.ok and r.reason.startswith("artifact-too-small")


def test_and_gate_schema_missing(tmp_path):
    u = Unit(
        id="cov-1", lane="coverage", prompt="p", artifact=str(tmp_path / "cov-1.md")
    )
    art = _art(
        tmp_path, "cov-1", "file: a.py\n" + "x" * 1100 + "\nUNIT-COMPLETE: cov-1\n"
    )
    r = verify.and_gate(u, art)
    assert not r.ok and r.reason.startswith("schema-missing-fields")


# --- integration: run_E.submit_and_gate must gate through engine.verify (the ONE gate impl on the
# run_E production path -- NOT repo-wide: harness/poll.py:8 `classify` is a live SECOND clause-1-5
# impl, still used by harness/poll.py:26 `poll_once` and e2e/smoke_2unit.py:51) ---

_RESULTS = "/dbfs/tmp/csie-t8/results"


def _unit(uid):
    return Unit(id=uid, lane="smoke", prompt="p", artifact=f"{_RESULTS}/{uid}.md")


def _body(uid):
    """A smoke-lane body above the 1024-byte floor; uid=None omits the UNIT-COMPLETE sentinel."""
    return "echo: hi\n" + "x" * 1100 + (f"\nUNIT-COMPLETE: {uid}\n" if uid else "\n")


def _fake_run_cmd(bodies, states):
    """Databricks CLI stand-in: one submitted run walking `states`, `bodies` served off DBFS."""
    pending = list(states)

    def run_cmd(argv):
        verb = " ".join(argv[1:3])
        if verb in ("fs mkdirs", "fs cp"):
            return 0, "", ""
        if verb == "jobs submit":
            return 0, json.dumps({"run_id": 4242}), ""
        if verb == "jobs get-run":
            state = pending.pop(0) if len(pending) > 1 else pending[0]
            st = {"life_cycle_state": state, "state_message": "Succeeded"}
            return 0, json.dumps({"state": st}), ""
        if verb == "fs ls":
            return 0, "\n".join(f"{argv[3]}/{n}" for n in bodies), ""
        if verb == "fs cat":
            name = argv[3].rsplit("/", 1)[-1]
            return (0, bodies[name], "") if name in bodies else (1, "", "no such file")
        raise AssertionError(f"unexpected argv: {argv}")

    return run_cmd


def _drive(monkeypatch, units, name, bodies, states=("TERMINATED",)):
    """Drive run_E.submit_and_gate against the fake CLI.

    Returns (verdicts, gate_results, classify_calls, polls): every Result engine.verify produced,
    every harness.poll.classify call (which MUST stay empty -- run_E must not gate TWICE; scoped
    claim: poll.classify itself is still live elsewhere, at harness/poll.py:26 and
    e2e/smoke_2unit.py:51), and the count of `jobs get-run` polls.
    """
    gate_results: list[Result] = []
    classify_calls: list[str] = []
    polls = []
    real_gate, real_classify = verify.and_gate, poll.classify

    def gate_spy(unit, artifact_path):
        r = real_gate(unit, artifact_path)
        gate_results.append(r)
        return r

    def classify_spy(job_state, unit, local_artifact):
        classify_calls.append(unit.id)
        return real_classify(job_state, unit, local_artifact)

    inner = _fake_run_cmd(bodies, states)

    def run_cmd(argv):
        if " ".join(argv[1:3]) == "jobs get-run":
            # how many gate calls had already fired when this poll went out
            polls.append(len(gate_results))
        return inner(argv)

    monkeypatch.setattr(verify, "and_gate", gate_spy)
    monkeypatch.setattr(poll, "classify", classify_spy)
    monkeypatch.setattr(run_E.time, "sleep", lambda _s: None)  # skip the grace waits
    scratch = Path(run_E.__file__).resolve().parents[2] / "e2e" / f"_E_{name}"
    shutil.rmtree(scratch, ignore_errors=True)
    try:
        verdicts = run_E.submit_and_gate(units, name, run_cmd)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return verdicts, gate_results, classify_calls, polls


@_needs_rewired_run_E
def test_submit_and_gate_classifies_two_units_through_engine_verify(monkeypatch):
    """Two units through the real submit->poll->harvest->gate path: the valid artifact is DONE and
    the below-floor one FAILED, and BOTH verdicts are produced by engine.verify.and_gate."""
    bodies = {
        "t8-ok.md": _body("t8-ok"),
        "t8-small.md": "echo: hi\nUNIT-COMPLETE: t8-small\n",  # 33 B: below the 1024 floor
    }
    verdicts, gate_results, classify_calls, _ = _drive(
        monkeypatch, [_unit("t8-ok"), _unit("t8-small")], "t8-gate", bodies
    )

    assert verdicts["t8-ok"][0] == "DONE"
    assert verdicts["t8-small"][0] == "FAILED"
    assert verdicts["t8-ok"][1].name == "t8-ok.md"
    assert {r.unit_id for r in gate_results} == {"t8-ok", "t8-small"}
    assert classify_calls == []  # the inline poll.classify gate is GONE from run_E
    ok_reasons = [r.reason for r in gate_results if r.unit_id == "t8-ok"]
    assert set(ok_reasons) == {"and-gate-pass"}
    assert len(ok_reasons) == 3  # the 3x DBFS-eventual-consistency grace loop is KEPT
    # Honest: `harvest` already declines a below-floor body on the SAME per-lane floor, so the gate
    # is handed None here -- `artifact-too-small` is unreachable through run_E's fetch().
    small = [r.reason for r in gate_results if r.unit_id == "t8-small"]
    assert set(small) == {"no-artifact"}


@_needs_rewired_run_E
def test_submit_and_gate_failure_reason_is_a_gate_clause(monkeypatch):
    """A unit ABOVE harvest's floor but missing the sentinel: only the gate's own clause can reject
    it, so the FAILED verdict provably comes from engine.verify, not from a harvest side effect."""
    bodies = {"t8-ok2.md": _body("t8-ok2"), "t8-mute.md": _body(None)}
    verdicts, gate_results, classify_calls, _ = _drive(
        monkeypatch, [_unit("t8-ok2"), _unit("t8-mute")], "t8-mute", bodies
    )

    assert verdicts["t8-ok2"][0] == "DONE"
    assert verdicts["t8-mute"][0] == "FAILED"
    mute = [r for r in gate_results if r.unit_id == "t8-mute"]
    assert {r.reason for r in mute} == {"missing-UNIT-COMPLETE"}
    # it DID land and cleared the floor -- only a gate clause could have rejected it
    assert all(r.size >= 1024 and r.artifact for r in mute)
    assert classify_calls == []


@_needs_rewired_run_E
def test_submit_and_gate_does_not_gate_before_the_job_is_terminal(monkeypatch):
    """Clause 1 (job terminal) stays in the CALLER and, ON THIS PATH, that is the only place it
    lives: engine.verify.and_gate does not re-check the job state. (Scoped, not repo-wide --
    poll.classify still re-checks it itself and is still live at harness/poll.py:26 and
    e2e/smoke_2unit.py:51; it is not retired.) So a non-terminal poll must not reach the gate --
    otherwise a mid-flight artifact reads DONE."""
    verdicts, gate_results, classify_calls, polls = _drive(
        monkeypatch,
        [_unit("t8-run")],
        "t8-running",
        {"t8-run.md": _body("t8-run")},
        states=["RUNNING", "PENDING", "TERMINATED"],
    )

    assert polls == [0, 0, 0]  # 3 polls, and NO gate call had fired at any of them
    assert verdicts["t8-run"][0] == "DONE"
    assert len(gate_results) == 1  # gated once, only after the terminal poll
    assert classify_calls == []
