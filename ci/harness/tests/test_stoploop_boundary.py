"""A1 permanent fix — Stop re-entrancy guard HOISTED to the dispatcher boundary.

Encodes the B2-RFC-operational §1.5 acceptance floor (T2/T4/T5/T7) as
dispatcher-BOUNDARY tests rather than module-local ones:

  * T2  — a re-entrant Stop (host set stop_hook_active) is allowed-through BEFORE
          any module runs, so NO module can re-inject additionalContext / block
          and re-trigger the host Stop counter (the "Stop 3/4" / 53k-token drain).
          Proven with a SYNTHETIC Stop-capable module that has no guard of its own.
  * T4  — every Stop terminal row carries redacted correlation IDs (session_id +
          invocation_id) plus raw/normalized re-entrancy, threaded through BOTH
          the normal path and the boundary short-circuit path.
  * T5  — a StopFailure is recorded DISTINCTLY from a benign re-entrant Stop and
          is NOT swallowed / mis-counted as a completion claim.
  * T5' — the whole-process Stop contract stays exit-0 / "{}\\n" / empty-stderr.

Plus: the correlation IDs are REDACTED (hashed/truncated), never raw.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from harness.adapters import render_output
from harness.dispatcher import HarnessDispatcher
from harness.models import HookResult
from harness.redaction import redact_id


# --------------------------------------------------------------------------- #
# Synthetic Stop-capable modules that WOULD re-open the loop if the guard were
# per-module instead of at the boundary. Neither carries its own re-entrancy
# guard — the boundary hoist is what must neutralize them.
# --------------------------------------------------------------------------- #
class _AlwaysInject:
    name = "synthetic_injector"

    def run(self, event):
        if getattr(event, "event", "") in {"Stop", "StopFailure"}:
            return HookResult.success(
                action="inject",
                reason_code="unverified_completion_claim",
                additional_context=["all tests pass — the re-inject that would loop"],
            )
        return HookResult.success()


class _AlwaysBlockOnStop:
    name = "synthetic_blocker"

    def run(self, event):
        if getattr(event, "event", "") in {"Stop", "StopFailure"}:
            return HookResult.success(
                action="block",
                reason_code="secret_literal",
                additional_context=["the block that would force another continue"],
            )
        return HookResult.success()


def _stop_payload(
    tmp_path,
    *,
    reentrant=False,
    session_id="sess-raw",
    invocation_id="inv-raw",
    last_message="Everything is fixed and done.",
):
    payload = {
        "session_id": session_id,
        "cwd": str(tmp_path),
        "hook_event_name": "Stop",
        "last_assistant_message": last_message,
    }
    if invocation_id is not None:  # None => host omits it, dispatcher mints one
        payload["invocation_id"] = invocation_id
    if reentrant:
        payload["stop_hook_active"] = True
    return payload


def _read_rows(state_root):
    text = (state_root / "terminal.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


# --------------------------------------------------------------------------- #
# T2 — re-entrant Stop is allowed-through at the boundary, NO context from ANY
# module (the loop cannot reproduce).
# --------------------------------------------------------------------------- #
def test_reentrant_stop_short_circuits_before_any_module(tmp_path):
    modules = [_AlwaysInject(), _AlwaysBlockOnStop()]
    dispatcher = HarnessDispatcher(modules=modules, state_root=tmp_path / "state")
    result = dispatcher.dispatch(
        _stop_payload(tmp_path, reentrant=True), provider="claude", event_name="Stop"
    )
    # Boundary guard forces allow/empty regardless of the inject AND block modules.
    assert result.action == "allow"
    assert result.reason_code == "ok"
    assert result.additional_context == []
    # The loop-exit: native render is exactly {} so the host does not re-fire Stop.
    assert render_output(result, provider="claude", event_name="Stop") == {}


def test_first_stop_may_inject_then_reentrant_stop_allows(tmp_path):
    # DISPATCHER invariant (not per-module): the first Stop MAY inject once; the
    # immediate re-entrant Stop MUST allow.
    dispatcher = HarnessDispatcher(modules=[_AlwaysInject()], state_root=tmp_path / "state")
    first = dispatcher.dispatch(_stop_payload(tmp_path), provider="claude", event_name="Stop")
    assert first.action == "inject"
    reentrant = dispatcher.dispatch(
        _stop_payload(tmp_path, reentrant=True), provider="claude", event_name="Stop"
    )
    assert reentrant.action == "allow"
    assert reentrant.additional_context == []


def test_non_reentrant_stop_still_runs_modules(tmp_path):
    # The guard must NOT weaken the first (non-re-entrant) Stop: a genuine
    # completion claim still gets its one-shot inject.
    dispatcher = HarnessDispatcher(modules=[_AlwaysInject()], state_root=tmp_path / "state")
    result = dispatcher.dispatch(_stop_payload(tmp_path), provider="claude", event_name="Stop")
    assert result.action == "inject"
    assert result.additional_context


# --------------------------------------------------------------------------- #
# T4 / T7 — correlation IDs present + threaded through both code paths.
# --------------------------------------------------------------------------- #
def test_stop_terminal_carries_correlation_ids_on_both_paths(tmp_path):
    state_root = tmp_path / "state"
    dispatcher = HarnessDispatcher(modules=[_AlwaysInject()], state_root=state_root)
    # invocation_id=None => host omits it, so the dispatcher mints a fresh id each
    # invocation (proves per-invocation uniqueness on the generated path).
    dispatcher.dispatch(
        _stop_payload(tmp_path, invocation_id=None), provider="claude", event_name="Stop"
    )  # normal path
    dispatcher.dispatch(
        _stop_payload(tmp_path, reentrant=True, invocation_id=None),
        provider="claude",
        event_name="Stop",
    )  # boundary short-circuit path
    rows = _read_rows(state_root)
    assert len(rows) == 2
    for row in rows:
        assert row["session_id"]  # present + non-empty on BOTH paths
        assert row["invocation_id"]
        assert "reentrant" in row and "stop_hook_active" in row
    normal, reentrant = rows
    # normalized (reentrant) + raw (stop_hook_active) re-entrancy both recorded.
    assert normal["reentrant"] is False and normal["stop_hook_active"] is False
    assert reentrant["reentrant"] is True and reentrant["stop_hook_active"] is True
    # Terminal status stays event-suffixed on the short-circuit path (uniform join).
    assert reentrant["terminal"] == "SUCCESS:hook-stop"
    # session_id is the loop-join key: STABLE across invocations (a Stop-storm is
    # correlatable); invocation_id is unique per invocation.
    assert normal["session_id"] == reentrant["session_id"]
    assert normal["invocation_id"] != reentrant["invocation_id"]


def test_terminal_correlation_ids_are_redacted_not_raw(tmp_path):
    state_root = tmp_path / "state"
    dispatcher = HarnessDispatcher(modules=[_AlwaysInject()], state_root=state_root)
    dispatcher.dispatch(
        _stop_payload(
            tmp_path,
            session_id="SENSITIVE-SESSION-abcdef123456",
            invocation_id="SENSITIVE-INVOCATION-zyxwvu987654",
        ),
        provider="claude",
        event_name="Stop",
    )
    text = (state_root / "terminal.jsonl").read_text(encoding="utf-8")
    # The RAW ids must NEVER land in the log verbatim.
    assert "SENSITIVE-SESSION-abcdef123456" not in text
    assert "SENSITIVE-INVOCATION-zyxwvu987654" not in text
    row = _read_rows(state_root)[0]
    # ...but a stable, non-empty redaction (hash/truncation) IS present.
    assert row["session_id"] and row["session_id"] != "SENSITIVE-SESSION-abcdef123456"
    assert row["invocation_id"] and row["invocation_id"] != "SENSITIVE-INVOCATION-zyxwvu987654"


def test_redact_id_is_stable_and_non_raw():
    assert redact_id("") == ""
    first = redact_id("session-xyz")
    assert first == redact_id("session-xyz")  # stable => correlatable
    assert first != "session-xyz"  # not the raw value
    assert len(first) >= 4
    assert redact_id("session-other") != first  # discriminates distinct ids


# --------------------------------------------------------------------------- #
# T5 — StopFailure distinguished from a benign re-entrant Stop, and NOT swallowed.
# --------------------------------------------------------------------------- #
def test_stopfailure_distinguished_and_not_swallowed(tmp_path):
    state_root = tmp_path / "state"
    # A synthetic inject-on-Stop/StopFailure module is present: a StopFailure must
    # be observe-only (never mis-counted as a completion claim) yet still recorded.
    dispatcher = HarnessDispatcher(modules=[_AlwaysInject()], state_root=state_root)
    sf = dispatcher.dispatch(
        {"session_id": "s", "cwd": str(tmp_path), "hook_event_name": "StopFailure"},
        provider="claude",
        event_name="StopFailure",
    )
    dispatcher.dispatch(
        _stop_payload(tmp_path, reentrant=True), provider="claude", event_name="Stop"
    )
    # Observe-only: NOT swallowed into a normal completion-claim inject.
    assert sf.action == "allow"
    assert sf.additional_context == []
    rows = _read_rows(state_root)
    sf_row = next(r for r in rows if r["event"] == "StopFailure")
    stop_row = next(r for r in rows if r["event"] == "Stop")
    # Distinguished: StopFailure carries its own reason_code, NOT the benign "ok".
    assert sf_row["reason_code"] == "stopfailure"
    assert sf_row["terminal"] == "SUCCESS:hook-stopfailure"
    assert stop_row["reason_code"] == "ok"
    # NOT swallowed: the StopFailure is attributable in telemetry (its own row).
    assert sf_row["reentrant"] is False
    assert sf_row["session_id"] and sf_row["invocation_id"]


# --------------------------------------------------------------------------- #
# T5' — whole-process Stop contract (exit 0, "{}\n", empty stderr).
# --------------------------------------------------------------------------- #
def test_reentrant_stop_subprocess_is_exit0_empty_json(tmp_path):
    script = Path(__file__).resolve().parents[1] / "dispatcher.py"
    payload = {
        "session_id": "sess",
        "cwd": str(tmp_path),
        "hook_event_name": "Stop",
        "stop_hook_active": True,
        "last_assistant_message": "Everything is fixed and done.",
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--provider",
            "claude",
            "--event",
            "Stop",
            "--state-root",
            str(tmp_path / "state"),
        ],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert completed.returncode == 0
    assert completed.stdout == "{}\n"
    assert completed.stderr.strip() == ""
