"""Regression tests: the dispatcher must never report a measurement it did not make.

Ported from the live harness tree in the 2026-09-02 lineage reunion. Four reproduced
defects, one theme -- terminal health has to describe what the fan-out ACTUALLY did:

1. An enforced-quarantine skip stamped ``SUCCESS`` with an empty
   ``failed_modules`` even though a safety detector never ran.
2. A corrupt ``breaker.json`` streak (externally written non-integer) raised out
   of ``_breaker_on_error`` INSIDE the except handler, so the ValueError escaped
   ``dispatch()`` entirely -- discarding an already-computed ``block`` and
   writing no terminal record at all (contradicting the fail-open contract).
3. Malformed / non-object stdin was erased to ``{}`` and then stamped
   ``SUCCESS``, so a hook that measured nothing looked healthy. The maintained
   tree already carried this fix under the D010 ``transport_error`` name (the
   failure class is recorded in ``failed_modules``); the live tree's
   ``input_error``/``malformed_input`` variant was NOT carried -- these tests pin
   the D010 shape so the two never drift apart again.
4. A module can outlive the host's registered hook deadline (2s on the hot
   events). The host SIGKILLs the process, so nothing is recorded and every
   later module is silently skipped. The fan-out now runs under a wall-clock
   budget and records the abandonment instead of vanishing.
"""

from __future__ import annotations

import io
import json
import time

from harness.dispatcher import (
    _MIN_BUDGET_SEC,
    _STARTUP_ALLOWANCE_SEC,
    HarnessDispatcher,
    _as_int,
    _dispatch_budget_sec,
    _host_deadline_sec,
    main,
)
from harness.models import HookResult


class _Module:
    def __init__(self, name, result):
        self.name = name
        self._result = result

    def run(self, _event):
        return self._result


class _Sleeper:
    name = "sleeper"

    def __init__(self, seconds: float):
        self.seconds = seconds

    def run(self, _event):
        time.sleep(self.seconds)
        return HookResult.success()


def _pre(tmp_path, command="echo safe"):
    return {
        "session_id": "s",
        "turn_id": "t",
        "cwd": str(tmp_path),
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "hook_event_name": "PreToolUse",
    }


def _records(state_root):
    path = state_root / "terminal.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _block(reason_code="secret_literal"):
    return HookResult.success(
        action="block", reason_code=reason_code, additional_context=["Blocked."]
    )


# --------------------------------------------------------------------------- #
# 1 - enforced quarantine must not report a healthy hook
# --------------------------------------------------------------------------- #
def test_quarantined_module_reports_degraded_not_success(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_BREAKER_MODE", "enforce")
    state_root = tmp_path / "state"
    state_root.mkdir(parents=True)
    (state_root / "breaker.json").write_text(
        json.dumps(
            {
                "modules": {
                    "secret_guard": {
                        "streak": 0,
                        "quarantined_until": time.time() + 9999,
                    }
                },
                "alerts": [],
            }
        ),
        encoding="utf-8",
    )
    guard = _Module("secret_guard", _block())
    dispatcher = HarnessDispatcher(modules=[guard], state_root=state_root)
    result = dispatcher.dispatch(
        _pre(tmp_path, "export TOKEN=sk-live-abcdefghijklmnop"),
        provider="claude",
        event_name="PreToolUse",
    )
    # The detector was skipped: the hook is DEGRADED, not a clean measurement.
    assert result.status == "FAILED:hook-pretooluse"
    record = _records(state_root)[-1]
    assert record["terminal"] == "FAILED:hook-pretooluse"
    assert "secret_guard" in record["failed_modules"]


def test_shadow_quarantine_still_runs_the_module_and_stays_healthy(
    tmp_path, monkeypatch
):
    # KNOWN-NEGATIVE control: in shadow mode nothing is skipped, so the same
    # breaker state must NOT degrade the record.
    monkeypatch.setenv("HARNESS_BREAKER_MODE", "shadow")
    state_root = tmp_path / "state"
    state_root.mkdir(parents=True)
    (state_root / "breaker.json").write_text(
        json.dumps(
            {
                "modules": {
                    "goal": {"streak": 0, "quarantined_until": time.time() + 9999}
                },
                "alerts": [],
            }
        ),
        encoding="utf-8",
    )
    dispatcher = HarnessDispatcher(
        modules=[_Module("goal", HookResult.success())], state_root=state_root
    )
    result = dispatcher.dispatch(
        _pre(tmp_path), provider="claude", event_name="PreToolUse"
    )
    assert result.status == "SUCCESS:hook-pretooluse"
    assert _records(state_root)[-1]["failed_modules"] == []


# --------------------------------------------------------------------------- #
# 2 - a corrupt breaker slot must not escape dispatch()
# --------------------------------------------------------------------------- #
def test_corrupt_breaker_streak_does_not_escape_dispatch(tmp_path):
    state_root = tmp_path / "state"
    state_root.mkdir(parents=True)
    (state_root / "breaker.json").write_text(
        json.dumps(
            {
                "modules": {"secret_guard": {"streak": "not-an-integer"}},
                "alerts": [],
            }
        ),
        encoding="utf-8",
    )
    dispatcher = HarnessDispatcher(
        modules=[_Module("secret_guard", _block())], state_root=state_root
    )
    # Before the fix this raised ValueError out of dispatch() (the except handler
    # itself re-raised), losing the deny and writing no terminal record.
    result = dispatcher.dispatch(
        _pre(tmp_path, "export TOKEN=sk-live-abcdefghijklmnop"),
        provider="claude",
        event_name="PreToolUse",
    )
    assert result.action == "block"
    assert result.reason_code == "secret_literal"
    assert _records(state_root)[-1]["action"] == "block"


def test_corrupt_breaker_streak_is_reset_by_a_success_not_raised(tmp_path):
    # The success path reads the same slot; a corrupt streak must degrade to 0
    # there too instead of raising out of the fan-out.
    state_root = tmp_path / "state"
    state_root.mkdir(parents=True)
    (state_root / "breaker.json").write_text(
        json.dumps(
            {"modules": {"goal": {"streak": ["nested", "garbage"]}}, "alerts": []}
        ),
        encoding="utf-8",
    )
    dispatcher = HarnessDispatcher(
        modules=[_Module("goal", HookResult.success())], state_root=state_root
    )
    result = dispatcher.dispatch(
        _pre(tmp_path), provider="claude", event_name="PreToolUse"
    )
    assert result.status == "SUCCESS:hook-pretooluse"


def test_as_int_degrades_garbage_to_the_default_and_keeps_numbers():
    assert _as_int(None) == 0
    assert _as_int("") == 0
    assert _as_int("7") == 7
    assert _as_int(3.9) == 3
    assert _as_int("not-an-integer") == 0
    assert _as_int({"streak": 1}, default=5) == 5
    assert _as_int(None, default=2) == 2


# --------------------------------------------------------------------------- #
# 3 - malformed stdin must not be stamped SUCCESS (D010 shape, kept from A)
# --------------------------------------------------------------------------- #
def _run_main(monkeypatch, tmp_path, stdin_text):
    state_root = tmp_path / "state"
    monkeypatch.setattr(
        "harness.dispatcher.build_default_modules",
        lambda _root: [_Module("noop", HookResult.success())],
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    rc = main(
        [
            "--provider",
            "claude",
            "--event",
            "PreToolUse",
            "--state-root",
            str(state_root),
        ]
    )
    return rc, _records(state_root)


def test_malformed_stdin_records_a_failed_terminal(monkeypatch, tmp_path):
    rc, records = _run_main(monkeypatch, tmp_path, "{not-json")
    assert rc == 0  # still fail-open for the host
    assert records[-1]["terminal"] == "FAILED:hook-pretooluse"
    assert records[-1]["reason_code"] == "internal_error"
    assert records[-1]["failed_modules"] == ["_transport:malformed_json"]


def test_non_object_stdin_records_a_failed_terminal(monkeypatch, tmp_path):
    _rc, records = _run_main(monkeypatch, tmp_path, '"just-a-string"')
    assert records[-1]["terminal"] == "FAILED:hook-pretooluse"
    assert records[-1]["reason_code"] == "internal_error"
    assert records[-1]["failed_modules"] == ["_transport:non_object_payload"]


def test_well_formed_stdin_still_reports_success(monkeypatch, tmp_path):
    _rc, records = _run_main(monkeypatch, tmp_path, json.dumps({"cwd": "."}))
    assert records[-1]["terminal"] == "SUCCESS:hook-pretooluse"
    assert records[-1]["reason_code"] == "ok"
    assert records[-1]["failed_modules"] == []


# --------------------------------------------------------------------------- #
# 4 - a module that outlives the host deadline must be abandoned + recorded
# --------------------------------------------------------------------------- #
def test_slow_module_is_abandoned_at_the_dispatch_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_DISPATCH_BUDGET_MS", "200")
    state_root = tmp_path / "state"
    dispatcher = HarnessDispatcher(modules=[_Sleeper(10.0)], state_root=state_root)
    started = time.perf_counter()
    result = dispatcher.dispatch(
        _pre(tmp_path), provider="claude", event_name="PreToolUse"
    )
    elapsed = time.perf_counter() - started
    # Bails at the budget instead of blocking until the host SIGKILLs us.
    assert elapsed < 3.0, f"dispatch blocked for {elapsed:.2f}s"
    assert result.action == "allow"  # fail-open
    assert result.status == "FAILED:hook-pretooluse"
    record = _records(state_root)[-1]
    assert "sleeper" in record["failed_modules"]


def test_finished_modules_survive_a_later_abandonment(tmp_path, monkeypatch):
    # The whole point of recording instead of vanishing: work the fast modules
    # completed before the budget expired still reaches the host.
    monkeypatch.setenv("HARNESS_DISPATCH_BUDGET_MS", "200")
    state_root = tmp_path / "state"
    dispatcher = HarnessDispatcher(
        modules=[
            _Module(
                "goal",
                HookResult.success(
                    action="inject",
                    reason_code="goal_reinjection",
                    additional_context=["ACTIVE GOAL: keep going"],
                ),
            ),
            _Sleeper(10.0),
        ],
        state_root=state_root,
    )
    result = dispatcher.dispatch(
        _pre(tmp_path), provider="claude", event_name="PreToolUse"
    )
    assert result.action == "inject"
    assert any("ACTIVE GOAL" in text for text in result.additional_context)
    assert result.status == "FAILED:hook-pretooluse"
    assert _records(state_root)[-1]["failed_modules"] == ["sleeper"]


def test_fast_modules_are_unaffected_by_the_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_DISPATCH_BUDGET_MS", "5000")
    state_root = tmp_path / "state"
    dispatcher = HarnessDispatcher(
        modules=[_Module("goal", HookResult.success(reason_code="goal_reinjection"))],
        state_root=state_root,
    )
    result = dispatcher.dispatch(
        _pre(tmp_path), provider="claude", event_name="PreToolUse"
    )
    assert result.status == "SUCCESS:hook-pretooluse"
    assert _records(state_root)[-1]["failed_modules"] == []


def test_budget_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_DISPATCH_BUDGET_MS", "0")
    state_root = tmp_path / "state"
    dispatcher = HarnessDispatcher(modules=[_Sleeper(0.05)], state_root=state_root)
    result = dispatcher.dispatch(
        _pre(tmp_path), provider="claude", event_name="PreToolUse"
    )
    assert result.status == "SUCCESS:hook-pretooluse"


def test_budget_tracks_the_registered_host_deadline(monkeypatch):
    monkeypatch.delenv("HARNESS_DISPATCH_BUDGET_MS", raising=False)
    # The budget has to leave the process room to start up and to write its
    # terminal record + native output INSIDE the host's registered timeout.
    # 2026-10-13/17 lockstep: registration._TIMEOUTS raised PreToolUse 2->25,
    # SessionStart 5->60 (RAM-starvation floor; see registration.py comment).
    assert _host_deadline_sec("PreToolUse") == 25.0  # registration._TIMEOUTS
    assert _dispatch_budget_sec("PreToolUse") == 25.0 - _STARTUP_ALLOWANCE_SEC
    assert _dispatch_budget_sec("SessionStart") == 60.0 - _STARTUP_ALLOWANCE_SEC
    # An event the harness does not register falls back to the 5s default.
    assert _host_deadline_sec("NoSuchEvent") == 5.0
    # A floor keeps the watchdog usable even if a deadline ever drops below it.
    monkeypatch.setattr("harness.dispatcher._STARTUP_ALLOWANCE_SEC", 99.0)
    assert _dispatch_budget_sec("PreToolUse") == _MIN_BUDGET_SEC


def test_unparseable_budget_override_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("HARNESS_DISPATCH_BUDGET_MS", "not-a-number")
    assert _dispatch_budget_sec("PreToolUse") == 25.0 - _STARTUP_ALLOWANCE_SEC


def test_negative_budget_override_disables_the_watchdog(monkeypatch):
    monkeypatch.setenv("HARNESS_DISPATCH_BUDGET_MS", "-50")
    assert _dispatch_budget_sec("PreToolUse") == 0.0
