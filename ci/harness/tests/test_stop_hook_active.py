"""Direct-invocation tests for the dispatcher's re-entrant Stop short-circuit.

`ci/harness` is ruff-EXCLUDED and has no pytest lane in CI, so this file doubles
as a runnable proof:

    python ci/harness/tests/test_stop_hook_active.py

runs the same assertions and prints a PASS/FAIL summary plus the observed
values. A spy module proves the short-circuit fires BEFORE any module runs
(defense-in-depth) and that ordinary Stop events fan out unchanged.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

_CI = Path(__file__).resolve().parent.parent.parent  # .../ci
if str(_CI) not in sys.path:
    sys.path.insert(0, str(_CI))

from harness.adapters import render_output  # noqa: E402
from harness.dispatcher import HarnessDispatcher  # noqa: E402
from harness.models import HookResult  # noqa: E402


class _SpyModule:
    """A module that records whether the dispatcher fanned out to it."""

    name = "spy"

    def __init__(self) -> None:
        self.calls = 0

    def run(self, event: Any) -> HookResult:
        self.calls += 1
        return HookResult.success()


def _dispatch(
    raw: dict[str, Any], event_name: str = "Stop"
) -> tuple[_SpyModule, HookResult, dict[str, Any]]:
    spy = _SpyModule()
    with tempfile.TemporaryDirectory() as tmp:
        dispatcher = HarnessDispatcher(modules=[spy], state_root=tmp)
        result = dispatcher.dispatch(raw, provider="claude", event_name=event_name)
        native = render_output(result, provider="claude", event_name=event_name)
    return spy, result, native


def test_reentrant_stop_short_circuits_before_modules() -> None:
    spy, result, native = _dispatch(
        {"hook_event_name": "Stop", "stop_hook_active": True}
    )
    assert result.action == "allow"  # never block / continue
    assert result.reason_code == "reentrant_stop"
    assert spy.calls == 0  # short-circuit fired BEFORE fan-out
    assert native == {}  # silent output


def test_reentrant_subagent_stop_short_circuits() -> None:
    spy, result, native = _dispatch(
        {"hook_event_name": "SubagentStop", "stop_hook_active": True},
        event_name="SubagentStop",
    )
    assert result.action == "allow"
    assert result.reason_code == "reentrant_stop"
    assert spy.calls == 0
    assert native == {}


def test_normal_stop_runs_modules() -> None:
    spy, result, _ = _dispatch({"hook_event_name": "Stop"})
    assert spy.calls == 1  # fan-out unchanged
    assert result.action == "allow"


def test_stop_hook_active_false_runs_modules() -> None:
    spy, result, _ = _dispatch({"hook_event_name": "Stop", "stop_hook_active": False})
    assert spy.calls == 1  # only a truthy flag short-circuits


def test_stop_hook_active_string_true_short_circuits() -> None:
    # Hosts may serialize the flag as a string; the guard normalizes it.
    spy, result, _ = _dispatch({"hook_event_name": "Stop", "stop_hook_active": "true"})
    assert spy.calls == 0
    assert result.reason_code == "reentrant_stop"


def test_stop_hook_active_ignored_off_stop_events() -> None:
    # The guard is scoped to Stop / SubagentStop; a stray flag on another event
    # must NOT suppress that event's modules.
    spy, _result, _native = _dispatch(
        {"hook_event_name": "PreToolUse", "stop_hook_active": True},
        event_name="PreToolUse",
    )
    assert spy.calls == 1


_CASES = (
    (
        "re-entrant Stop -> silent, modules skipped",
        test_reentrant_stop_short_circuits_before_modules,
    ),
    ("re-entrant SubagentStop -> silent", test_reentrant_subagent_stop_short_circuits),
    ("normal Stop -> modules run (unchanged)", test_normal_stop_runs_modules),
    ("stop_hook_active=false -> modules run", test_stop_hook_active_false_runs_modules),
    (
        "stop_hook_active='true' (string) -> silent",
        test_stop_hook_active_string_true_short_circuits,
    ),
    ("flag ignored on non-Stop events", test_stop_hook_active_ignored_off_stop_events),
)


def _demo() -> None:
    print(
        "=== (a) re-entrant Stop: {'hook_event_name':'Stop','stop_hook_active':true} ==="
    )
    spy, result, native = _dispatch(
        {"hook_event_name": "Stop", "stop_hook_active": True}
    )
    print(f"    module.calls = {spy.calls}   (expect 0: short-circuit BEFORE fan-out)")
    print(
        f"    action       = {result.action!r}   (expect 'allow'; never block/continue)"
    )
    print(f"    reason_code  = {result.reason_code!r}")
    print(f"    native out   = {native!r}   (expect {{}}: silent)")
    print("=== (b) normal Stop: {'hook_event_name':'Stop'} ===")
    spy2, result2, native2 = _dispatch({"hook_event_name": "Stop"})
    print(f"    module.calls = {spy2.calls}   (expect 1: fan-out unchanged)")
    print(f"    action       = {result2.action!r}   (expect 'allow')")
    print(f"    native out   = {native2!r}")


if __name__ == "__main__":
    _demo()
    print("--- assertions ---")
    failures = 0
    for _name, _fn in _CASES:
        try:
            _fn()
            print(f"PASS: {_name}")
        except AssertionError as exc:  # pragma: no cover - direct-run reporting
            failures += 1
            print(f"FAIL: {_name}: {exc}")
    total = len(_CASES)
    if failures:
        print(f"FAILED:stop-hook-active-tests {failures}/{total} failed")
    else:
        print(f"SUCCESS:stop-hook-active-tests {total}/{total} passed")
    raise SystemExit(1 if failures else 0)
