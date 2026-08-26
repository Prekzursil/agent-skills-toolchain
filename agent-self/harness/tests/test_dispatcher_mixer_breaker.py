"""Tests for the G3 injection-mixer, F6 guard-liveness circuit-breaker, and the
F2 dispatcher-half guarantees folded into dispatcher.py.

Every folded gem ships SHADOW by default (observe + log only): the mixer never
drops context and the breaker never skips a module until explicitly promoted to
enforce via its env flag. These tests assert both the shadow-default (behaviour
preserved) and the enforce-mode mechanics, plus the fail-open contract and the
per-branch isolation mandate (a raised exception in one module never suppresses a
later module).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import harness.modules as harness_modules
from harness.dispatcher import (
    HarnessDispatcher,
    PRIORITY_ADVISORY,
    PRIORITY_GOAL,
    PRIORITY_LOOP,
    PRIORITY_SAFETY,
    PRIORITY_VERIFY,
    _inject_priority,
    _sterile_cockpit,
    mix_injections,
    normalize_event,
)
from harness.models import HookResult


# --------------------------------------------------------------------------- #
# Stub modules
# --------------------------------------------------------------------------- #
class _Module:
    def __init__(self, name, result):
        self.name = name
        self._result = result

    def run(self, _event):
        return self._result


class _Exploding:
    def __init__(self, name="exploder"):
        self.name = name

    def run(self, _event):
        raise RuntimeError("sensitive internal detail")


def _inject(reason_code, text, action="inject"):
    return HookResult.success(
        action=action, reason_code=reason_code, additional_context=[text]
    )


def _pre(tmp_path, command="echo safe"):
    return {
        "session_id": "s",
        "turn_id": "t",
        "cwd": str(tmp_path),
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "hook_event_name": "PreToolUse",
    }


_BREAKER_CHILD = r"""
import json
import os
import time
from pathlib import Path

from harness.dispatcher import HarnessDispatcher


class _Boom:
    name = os.environ["HARNESS_TEST_MODULE_NAME"]

    def run(self, _event):
        raise RuntimeError("boom")


ready = Path(os.environ["HARNESS_TEST_READY_PATH"])
release = Path(os.environ["HARNESS_TEST_RELEASE_PATH"])
payload = json.loads(os.environ["HARNESS_TEST_EVENT"])
ready.write_text("ready", encoding="ascii")
deadline = time.monotonic() + 5.0
while not release.exists():
    if time.monotonic() >= deadline:
        raise TimeoutError("parent did not release breaker race child")
    time.sleep(0.01)
HarnessDispatcher(modules=[_Boom()], state_root=Path(os.environ["HARNESS_TEST_STATE_ROOT"])).dispatch(
    payload,
    provider="codex",
    event_name="PreToolUse",
)
"""


def _child_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    agent_self = Path(__file__).resolve().parents[2]
    prior_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(agent_self), prior_pythonpath) if part
    )
    env["HARNESS_TEST_STATE_ROOT"] = str(tmp_path / "state")
    return env


def _wait_for_ready(process: subprocess.Popen[str], ready_path: Path) -> None:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if ready_path.is_file():
            return
        if process.poll() is not None:
            break
        time.sleep(0.01)
    if process.poll() is None:
        process.kill()
    _stdout, stderr = process.communicate(timeout=5)
    raise AssertionError(
        "breaker child did not become ready "
        f"(returncode={process.returncode}, stderr={stderr!r})"
    )


# --------------------------------------------------------------------------- #
# SI-4 priority mapping
# --------------------------------------------------------------------------- #
def test_inject_priority_maps_each_family():
    assert _inject_priority("secret_literal") == PRIORITY_SAFETY
    assert _inject_priority("config_drift") == PRIORITY_SAFETY
    assert _inject_priority("goal_reinjection") == PRIORITY_GOAL
    assert _inject_priority("subagent_handoff") == PRIORITY_GOAL
    assert _inject_priority("unverified_completion_claim") == PRIORITY_VERIFY
    assert _inject_priority("repeated_no_progress") == PRIORITY_LOOP
    assert _inject_priority("lexical_recall") == PRIORITY_ADVISORY
    # unmapped / "ok" (the design-tool reminder emits "ok") -> advisory default
    assert _inject_priority("ok") == PRIORITY_ADVISORY
    assert _inject_priority("brand_new_unknown_code") == PRIORITY_ADVISORY


# --------------------------------------------------------------------------- #
# mix_injections pure function
# --------------------------------------------------------------------------- #
def test_mix_sorts_descending_by_priority_stable():
    items = [
        (PRIORITY_ADVISORY, "lexical_recall", "advisory"),
        (PRIORITY_SAFETY, "secret_literal", "safety"),
        (PRIORITY_GOAL, "goal_reinjection", "goal"),
    ]
    assert mix_injections(items, has_safety=False, sterile=False) == [
        "safety",
        "goal",
        "advisory",
    ]


def test_mix_stable_within_equal_priority():
    items = [
        (PRIORITY_ADVISORY, "lexical_recall", "first"),
        (PRIORITY_ADVISORY, "budget_pacing", "second"),
    ]
    assert mix_injections(items, has_safety=False, sterile=False) == ["first", "second"]


def test_mix_sidechain_ducks_advisory_when_safety_present():
    items = [
        (PRIORITY_ADVISORY, "lexical_recall", "advisory chatter"),
        (PRIORITY_SAFETY, "secret_literal", "SAFETY block message"),
        (PRIORITY_VERIFY, "unverified_completion_claim", "verify note"),
    ]
    mixed = mix_injections(items, has_safety=True, sterile=False)
    assert "advisory chatter" not in mixed
    assert mixed == ["SAFETY block message", "verify note"]


def test_mix_does_not_duck_without_safety():
    items = [
        (PRIORITY_ADVISORY, "lexical_recall", "advisory chatter"),
        (PRIORITY_GOAL, "goal_reinjection", "goal"),
    ]
    mixed = mix_injections(items, has_safety=False, sterile=False)
    assert "advisory chatter" in mixed


def test_mix_sterile_cockpit_keeps_only_safety():
    items = [
        (PRIORITY_SAFETY, "secret_literal", "safety"),
        (PRIORITY_GOAL, "goal_reinjection", "goal"),
        (PRIORITY_ADVISORY, "lexical_recall", "advisory"),
    ]
    assert mix_injections(items, has_safety=True, sterile=True) == ["safety"]


def test_mix_sterile_cockpit_can_mute_everything():
    items = [(PRIORITY_GOAL, "goal_reinjection", "goal")]
    assert mix_injections(items, has_safety=False, sterile=True) == []


def test_mix_total_cap_truncates_lowest_priority_first():
    items = [
        (PRIORITY_SAFETY, "secret_literal", "S" * 100),
        (PRIORITY_ADVISORY, "lexical_recall", "A" * 100),
    ]
    mixed = mix_injections(items, has_safety=False, sterile=False, total_cap=150)
    # safety kept whole; advisory truncated to the remaining 50 chars
    assert mixed[0] == "S" * 100
    assert mixed[1] == "A" * 50
    assert sum(len(part) for part in mixed) <= 150


def test_mix_total_cap_drops_when_no_budget_left():
    items = [
        (PRIORITY_SAFETY, "secret_literal", "S" * 100),
        (PRIORITY_ADVISORY, "lexical_recall", "A" * 100),
    ]
    mixed = mix_injections(items, has_safety=False, sterile=False, total_cap=100)
    assert mixed == ["S" * 100]


def test_mix_empty_input():
    assert mix_injections([], has_safety=True, sterile=True) == []


# --------------------------------------------------------------------------- #
# sterile-cockpit detection
# --------------------------------------------------------------------------- #
def _event(command, event_name="PreToolUse"):
    return normalize_event(
        {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "hook_event_name": event_name,
        },
        provider="claude",
        event_name=event_name,
    )


def test_sterile_cockpit_detects_commit_push_release_deploy():
    assert _sterile_cockpit(_event("git commit -m x"))
    assert _sterile_cockpit(_event("git push origin main"))
    assert _sterile_cockpit(_event("gh release create v1"))
    assert _sterile_cockpit(_event("./deploy.sh prod"))


def test_sterile_cockpit_ignores_ordinary_commands():
    assert not _sterile_cockpit(_event("pytest -q"))
    assert not _sterile_cockpit(_event("git status"))
    assert not _sterile_cockpit(
        _event("echo deployment note")
    )  # 'deployment' != 'deploy'


def test_sterile_cockpit_only_pretooluse():
    assert not _sterile_cockpit(_event("git push", event_name="PostToolUse"))


# --------------------------------------------------------------------------- #
# Dispatcher: SHADOW default preserves behaviour
# --------------------------------------------------------------------------- #
def test_shadow_default_preserves_context_under_block(tmp_path):
    modules = [
        _Module("advisory", _inject("lexical_recall", "advisory chatter")),
        _Module(
            "secret_guard",
            HookResult.success(
                action="block",
                reason_code="secret_literal",
                additional_context=["Blocked."],
            ),
        ),
    ]
    dispatcher = HarnessDispatcher(modules=modules, state_root=tmp_path / "state")
    result = dispatcher.dispatch(
        _pre(tmp_path), provider="claude", event_name="PreToolUse"
    )
    # SHADOW default: nothing dropped, module order preserved.
    assert result.action == "block"
    assert result.additional_context == ["advisory chatter", "Blocked."]


def test_shadow_logs_delta_without_altering_output(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        harness_modules, "shadow_log", lambda *a, **k: calls.append(a), raising=False
    )
    modules = [
        _Module("advisory", _inject("lexical_recall", "advisory chatter")),
        _Module(
            "secret_guard",
            HookResult.success(
                action="block",
                reason_code="secret_literal",
                additional_context=["Blocked."],
            ),
        ),
    ]
    dispatcher = HarnessDispatcher(modules=modules, state_root=tmp_path / "state")
    result = dispatcher.dispatch(
        _pre(tmp_path), provider="claude", event_name="PreToolUse"
    )
    assert result.additional_context == ["advisory chatter", "Blocked."]
    # The mixer would have ducked the advisory, so a delta is logged in shadow.
    assert any(a and a[0] == "injection_mixer" for a in calls)


# --------------------------------------------------------------------------- #
# Dispatcher: ENFORCE mode mechanics
# --------------------------------------------------------------------------- #
def test_enforce_mode_ducks_advisory_under_block(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_INJECT_MIXER", "enforce")
    modules = [
        _Module("advisory", _inject("lexical_recall", "advisory chatter")),
        _Module(
            "secret_guard",
            HookResult.success(
                action="block",
                reason_code="secret_literal",
                additional_context=["Blocked."],
            ),
        ),
    ]
    dispatcher = HarnessDispatcher(modules=modules, state_root=tmp_path / "state")
    result = dispatcher.dispatch(
        _pre(tmp_path), provider="claude", event_name="PreToolUse"
    )
    assert result.action == "block"
    assert result.additional_context == ["Blocked."]


def test_enforce_mode_sterile_cockpit_mutes_nonsafety_on_push(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_INJECT_MIXER", "enforce")
    modules = [_Module("goal", _inject("goal_reinjection", "re-anchor the goal"))]
    dispatcher = HarnessDispatcher(modules=modules, state_root=tmp_path / "state")
    result = dispatcher.dispatch(
        _pre(tmp_path, command="git push origin main"),
        provider="claude",
        event_name="PreToolUse",
    )
    # Non-safety goal inject muted during a push.
    assert result.additional_context == []


def test_enforce_mode_keeps_goal_when_not_sterile(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_INJECT_MIXER", "enforce")
    modules = [_Module("goal", _inject("goal_reinjection", "re-anchor the goal"))]
    dispatcher = HarnessDispatcher(modules=modules, state_root=tmp_path / "state")
    result = dispatcher.dispatch(
        _pre(tmp_path, command="pytest -q"), provider="claude", event_name="PreToolUse"
    )
    assert result.additional_context == ["re-anchor the goal"]


# --------------------------------------------------------------------------- #
# F6 circuit-breaker
# --------------------------------------------------------------------------- #
def test_breaker_records_streak_and_quarantines_after_threshold(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_BREAKER_STREAK", "2")
    state_root = tmp_path / "state"
    dispatcher = HarnessDispatcher(modules=[_Exploding("boom")], state_root=state_root)
    for _ in range(2):
        dispatcher.dispatch(_pre(tmp_path), provider="codex", event_name="PreToolUse")
    breaker = json.loads((state_root / "breaker.json").read_text(encoding="utf-8"))
    slot = breaker["modules"]["boom"]
    assert float(slot["quarantined_until"]) > 0
    assert any(alert["kind"] == "breaker_quarantine" for alert in breaker["alerts"])
    assert "heartbeat" in breaker


def test_breaker_success_resets_streak(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_BREAKER_STREAK", "3")
    state_root = tmp_path / "state"

    # A module that fails once then succeeds: streak must not accumulate to quarantine.
    class _Flaky:
        name = "flaky"

        def __init__(self):
            self.calls = 0

        def run(self, _event):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient")
            return HookResult.success()

    flaky = _Flaky()
    dispatcher = HarnessDispatcher(modules=[flaky], state_root=state_root)
    for _ in range(4):
        dispatcher.dispatch(_pre(tmp_path), provider="codex", event_name="PreToolUse")
    breaker = json.loads((state_root / "breaker.json").read_text(encoding="utf-8"))
    slot = breaker["modules"]["flaky"]
    assert float(slot.get("quarantined_until") or 0) == 0
    assert int(slot.get("streak") or 0) == 0


def test_breaker_enforce_skips_quarantined_module(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_BREAKER_STREAK", "1")
    monkeypatch.setenv("HARNESS_BREAKER_MODE", "enforce")
    state_root = tmp_path / "state"

    class _CountingExploder:
        name = "boom"

        def __init__(self):
            self.calls = 0

        def run(self, _event):
            self.calls += 1
            raise RuntimeError("crash")

    exploder = _CountingExploder()
    dispatcher = HarnessDispatcher(modules=[exploder], state_root=state_root)
    # First dispatch: runs, crashes, streak hits 1 -> quarantined.
    dispatcher.dispatch(_pre(tmp_path), provider="codex", event_name="PreToolUse")
    assert exploder.calls == 1
    # Second dispatch: quarantined -> skipped entirely (no further call).
    dispatcher.dispatch(_pre(tmp_path), provider="codex", event_name="PreToolUse")
    assert exploder.calls == 1


def test_breaker_spike_alarm(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_FAILED_SPIKE", "2")
    state_root = tmp_path / "state"
    modules = [_Exploding("a"), _Exploding("b"), _Exploding("c")]
    dispatcher = HarnessDispatcher(modules=modules, state_root=state_root)
    dispatcher.dispatch(_pre(tmp_path), provider="codex", event_name="PreToolUse")
    breaker = json.loads((state_root / "breaker.json").read_text(encoding="utf-8"))
    spikes = [a for a in breaker["alerts"] if a["kind"] == "failed_modules_spike"]
    assert spikes and spikes[-1]["detail"] == 3


def test_breaker_off_mode_writes_no_state(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_BREAKER_MODE", "off")
    state_root = tmp_path / "state"
    dispatcher = HarnessDispatcher(modules=[_Exploding("boom")], state_root=state_root)
    dispatcher.dispatch(_pre(tmp_path), provider="codex", event_name="PreToolUse")
    assert not (state_root / "breaker.json").exists()


def test_breaker_emits_telemetry_via_shadow_log(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_BREAKER_STREAK", "1")
    calls = []
    monkeypatch.setattr(
        harness_modules, "shadow_log", lambda *a, **k: calls.append(a), raising=False
    )
    dispatcher = HarnessDispatcher(
        modules=[_Exploding("boom")], state_root=tmp_path / "state"
    )
    dispatcher.dispatch(_pre(tmp_path), provider="codex", event_name="PreToolUse")
    assert any(a and a[0] == "guard_breaker" for a in calls)


# --------------------------------------------------------------------------- #
# F2 dispatcher-half guarantees + fail-open + per-branch isolation
# --------------------------------------------------------------------------- #
def test_terminal_jsonl_record_shape_is_unperturbed(tmp_path):
    modules = [_Module("noop", HookResult.success())]
    state_root = tmp_path / "state"
    dispatcher = HarnessDispatcher(modules=modules, state_root=state_root)
    dispatcher.dispatch(_pre(tmp_path), provider="claude", event_name="PreToolUse")
    line = (state_root / "terminal.jsonl").read_text(encoding="utf-8").strip()
    record = json.loads(line)
    # Exactly the pre-existing fields — no breaker/mixer keys leak into terminal.jsonl.
    assert set(record.keys()) == {
        "ts",
        "terminal",
        "provider",
        "event",
        "action",
        "reason_code",
        "elapsed_ms",
        "failed_modules",
    }
    assert record["terminal"] == "SUCCESS:hook-pretooluse"


def test_fail_open_preserved_with_breaker(tmp_path):
    dispatcher = HarnessDispatcher(
        modules=[_Exploding("boom")], state_root=tmp_path / "state"
    )
    result = dispatcher.dispatch(
        _pre(tmp_path), provider="codex", event_name="PreToolUse"
    )
    assert result.action == "allow"
    assert result.status.startswith("FAILED:")
    assert result.reason_code == "internal_error"
    assert "sensitive internal detail" not in " ".join(result.additional_context)


def test_raised_branch_does_not_suppress_later_module(tmp_path):
    modules = [
        _Exploding("boom"),
        _Module("goal", _inject("goal_reinjection", "still injected")),
    ]
    dispatcher = HarnessDispatcher(modules=modules, state_root=tmp_path / "state")
    result = dispatcher.dispatch(
        _pre(tmp_path), provider="codex", event_name="PreToolUse"
    )
    # The exploder failed but the later inject survived (per-branch isolation).
    assert "still injected" in result.additional_context
    assert result.action == "inject"
    assert result.status.startswith("FAILED:")


def test_timeout_stops_before_later_modules_and_discards_late_worker_state(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("HARNESS_DISPATCH_BUDGET_MS", "25")

    class _Slow:
        name = "slow"

        def __init__(self):
            self.started = threading.Event()
            self.release = threading.Event()

        def run(self, _event):
            self.started.set()
            self.release.wait(timeout=1.0)
            return _inject("goal_reinjection", "late slow context")

    class _Later:
        name = "later"

        def __init__(self):
            self.calls = 0

        def run(self, _event):
            self.calls += 1
            return _inject("goal_reinjection", "late later context")

    slow = _Slow()
    later = _Later()

    dispatcher = HarnessDispatcher(
        modules=[slow, later],
        state_root=tmp_path / "state",
    )

    result = dispatcher.dispatch(
        _pre(tmp_path), provider="codex", event_name="PreToolUse"
    )
    assert slow.started.is_set()
    assert result.status.startswith("FAILED:")
    assert "late later context" not in result.additional_context
    assert later.calls == 0


def test_shadow_default_no_shadow_log_is_safe(tmp_path, monkeypatch):
    # Simulate the modules lane not yet landing shadow_log: the fallback no-op must
    # keep the dispatcher fully working.
    monkeypatch.delattr(harness_modules, "shadow_log", raising=False)
    modules = [
        _Module("advisory", _inject("lexical_recall", "advisory chatter")),
        _Module(
            "secret_guard",
            HookResult.success(
                action="block",
                reason_code="secret_literal",
                additional_context=["Blocked."],
            ),
        ),
    ]
    dispatcher = HarnessDispatcher(modules=modules, state_root=tmp_path / "state")
    result = dispatcher.dispatch(
        _pre(tmp_path), provider="claude", event_name="PreToolUse"
    )
    assert result.additional_context == ["advisory chatter", "Blocked."]


def test_malformed_hook_result_fields_fail_open_instead_of_false_success(tmp_path):
    class _MalformedResult:
        name = "malformed"

        def run(self, _event):
            return HookResult(
                status="SUCCESS:hook-pretooluse",
                action="bogus",
                reason_code="ok",
                additional_context=[],
                continuation=None,
            )

    dispatcher = HarnessDispatcher(
        modules=[_MalformedResult()], state_root=tmp_path / "state"
    )
    result = dispatcher.dispatch(
        _pre(tmp_path), provider="codex", event_name="PreToolUse"
    )
    assert result.action == "allow"
    assert result.status.startswith("FAILED:")
    assert result.reason_code == "internal_error"


def test_module_name_error_still_marks_failed_and_honors_later_block(tmp_path):
    class _BadName:
        @property
        def name(self):
            raise RuntimeError("metadata broke")

        def run(self, _event):
            return _inject("goal_reinjection", "should not escape")

    class _Blocker:
        name = "blocker"

        def run(self, _event):
            return HookResult.success(
                action="block",
                reason_code="secret_literal",
                additional_context=["blocked later"],
            )

    dispatcher = HarnessDispatcher(
        modules=[_BadName(), _Blocker()], state_root=tmp_path / "state"
    )
    result = dispatcher.dispatch(
        _pre(tmp_path), provider="codex", event_name="PreToolUse"
    )
    assert result.action == "block"
    assert result.reason_code == "secret_literal"
    assert result.status.startswith("FAILED:")
    assert result.additional_context == ["blocked later"]


def test_breaker_finalize_merges_parallel_process_updates(tmp_path):
    release = tmp_path / "release"
    env_base = _child_env(tmp_path)
    payload = json.dumps(_pre(tmp_path))
    children: list[tuple[subprocess.Popen[str], Path]] = []
    try:
        for index, module_name in enumerate(("alpha", "beta")):
            ready = tmp_path / f"ready-{index}"
            env = env_base.copy()
            env["HARNESS_TEST_READY_PATH"] = str(ready)
            env["HARNESS_TEST_RELEASE_PATH"] = str(release)
            env["HARNESS_TEST_EVENT"] = payload
            env["HARNESS_TEST_MODULE_NAME"] = module_name
            process = subprocess.Popen(
                [sys.executable, "-c", _BREAKER_CHILD],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            children.append((process, ready))
        for process, ready in children:
            _wait_for_ready(process, ready)
        release.write_text("go", encoding="ascii")
        for process, _ready in children:
            stdout, stderr = process.communicate(timeout=5)
            assert process.returncode == 0, (stdout, stderr)
    finally:
        for process, _ready in children:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)

    breaker = json.loads(
        (tmp_path / "state" / "breaker.json").read_text(encoding="utf-8")
    )
    assert breaker["modules"]["alpha"]["streak"] == 1
    assert breaker["modules"]["beta"]["streak"] == 1
