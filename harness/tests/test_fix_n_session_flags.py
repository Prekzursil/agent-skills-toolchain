"""FIX-N regression tests: the basic-memory nudge must be SESSION-scoped.

Measured 2026-08-07: the pre-existing suite passes 730/730 against FOUR different
implementations of this gate - the unfixed one, two broken FIX-N variants, and the
correct one. Every assertion below is therefore a hole the old suite did not cover;
each one FAILS on at least one of those variants.

  test_sibling_session_bm_write_does_not_mute_this_session
      FAILS on the unfixed tree and on both `flag OR ledger` FIX-N variants.
  test_nudge_survives_ledger_eviction_of_the_canonical_edit
      FAILS on the unfixed tree (the root cause FIX-N exists to repair).
  test_own_bm_write_mutes_after_ledger_eviction
      FAILS on the unfixed tree.
  test_unidentified_session_shares_no_flag_directory
      FAILS on FIX-N without the "unknown" guard (goal-bleed class).
  test_unidentified_session_keeps_a_once_per_session_cooldown
      FAILS on FIX-N with the guard but no fallback cooldown (nags every Stop).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from harness.adapters import normalize_event
from harness.ledger import EventLedger
from harness.modules import ClaimWarningModule, LedgerModule

# adapters.py defaults a MISSING session_id to the literal "unknown", so every
# unidentified session hashes to this one digest.
UNKNOWN_DIGEST = hashlib.sha256(b"unknown").hexdigest()[:16]


@pytest.fixture
def iso(monkeypatch, tmp_path):
    """Redirect default_state_root() and the canonical-tree root into tmp."""
    root = tmp_path / "_hstate"
    monkeypatch.setenv("AGENT_HARNESS_STATE_ROOT", str(root))
    monkeypatch.setenv("HARNESS_LIVE_AGENTS_DIR", str(tmp_path / "agents"))
    monkeypatch.setenv("HARNESS_GATE_MODE__basic_memory_nudge", "enforce")
    return root


def _event(tmp_path: Path, name: str, **overrides):
    raw = {
        "session_id": "session-1",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "hook_event_name": name,
    }
    raw.update(overrides)
    return normalize_event(raw, provider="codex", event_name=name)


def _canonical_write(ledger, tmp_path, *, use_id="w1", session="session-1"):
    LedgerModule(ledger).run(
        _event(
            tmp_path,
            "PostToolUse",
            session_id=session,
            tool_name="Write",
            tool_use_id=use_id,
            tool_input={
                "file_path": str(tmp_path / "agents" / "harness" / "x.py"),
                "content": "y",
            },
            tool_response={"ok": True},
        )
    )


def _bm_write(ledger, tmp_path, *, use_id="bm1", session="session-1"):
    LedgerModule(ledger).run(
        _event(
            tmp_path,
            "PostToolUse",
            session_id=session,
            tool_name="mcp__basic-memory__write_note",
            tool_use_id=use_id,
            tool_input={"title": "t"},
            tool_response={"ok": True},
        )
    )


def _evict(ledger, tmp_path, count=130):
    """Push the earlier rows out of the bounded replay(cwd, limit=120) window."""
    for i in range(count):
        ledger.append(
            str(tmp_path), "tool_result", dedupe_key=f"filler-{i}", tool="Read"
        )


def test_sibling_session_bm_write_does_not_mute_this_session(iso, tmp_path):
    # The ledger is PROJECT-keyed and stores no session_id, so a basic-memory
    # write by ANOTHER session sharing this cwd sits in our replay window. It
    # must not be read as "this session captured the why".
    ledger = EventLedger(tmp_path / "state")
    _bm_write(ledger, tmp_path, use_id="bmS", session="session-SIBLING")
    _canonical_write(ledger, tmp_path, session="session-1")
    out = ClaimWarningModule(ledger).run(
        _event(tmp_path, "Stop", session_id="session-1")
    )
    assert out.action == "inject" and out.reason_code == "basic_memory_nudge"


def test_nudge_survives_ledger_eviction_of_the_canonical_edit(iso, tmp_path):
    # 85% of real canonical edits already carry >=120 later events in their own
    # shard by the time Stop fires; the bounded window is minutes, a session is
    # hours. The sticky per-session flag is what keeps the fact alive.
    ledger = EventLedger(tmp_path / "state")
    _canonical_write(ledger, tmp_path)
    _evict(ledger, tmp_path)
    out = ClaimWarningModule(ledger).run(_event(tmp_path, "Stop"))
    assert out.action == "inject" and out.reason_code == "basic_memory_nudge"


def test_own_bm_write_mutes_after_ledger_eviction(iso, tmp_path):
    # The suppression side must be just as durable as the firing side, or the
    # gate starts nagging sessions that DID capture the why.
    ledger = EventLedger(tmp_path / "state")
    _canonical_write(ledger, tmp_path)
    _bm_write(ledger, tmp_path)
    _evict(ledger, tmp_path)
    out = ClaimWarningModule(ledger).run(_event(tmp_path, "Stop"))
    assert out.action == "allow"


def test_unidentified_session_shares_no_flag_directory(iso, tmp_path):
    # A session with no session_id normalizes to "unknown". Writing its flags
    # under sha256("unknown") would make every anonymous session share one slot.
    ledger = EventLedger(tmp_path / "state")
    _canonical_write(ledger, tmp_path, session="unknown")
    ClaimWarningModule(ledger).run(_event(tmp_path, "Stop", session_id="unknown"))
    assert not (iso / "session-flags" / UNKNOWN_DIGEST).exists()


def test_unidentified_session_keeps_a_once_per_session_cooldown(iso, tmp_path):
    # Rejecting "unknown" must not cost the cooldown: without a fallback the gate
    # would re-nag at every single Stop of an unidentified session.
    ledger = EventLedger(tmp_path / "state")
    _canonical_write(ledger, tmp_path, session="unknown")
    module = ClaimWarningModule(ledger)
    first = module.run(_event(tmp_path, "Stop", session_id="unknown"))
    second = module.run(_event(tmp_path, "Stop", session_id="unknown"))
    assert first.action == "inject" and first.reason_code == "basic_memory_nudge"
    assert second.action == "allow"


def test_cooldown_survives_a_mid_session_carrier_flip(iso, tmp_path):
    # A session can START on the FALLBACK carrier (fired from a sibling's canonical
    # edit in the shared, project-keyed ledger window, cooled down by the marker
    # file) and only LATER make its own canonical edit, which creates the sticky
    # flag directory. If the sticky cooldown read ignores the marker, the
    # once-per-session cap is lost and the gate nags a second time.
    ledger = EventLedger(tmp_path / "state")
    module = ClaimWarningModule(ledger)
    _canonical_write(ledger, tmp_path, use_id="wSIB", session="session-SIBLING")
    first = module.run(_event(tmp_path, "Stop", session_id="session-1"))
    _canonical_write(ledger, tmp_path, use_id="wOWN", session="session-1")
    second = module.run(_event(tmp_path, "Stop", session_id="session-1"))
    assert first.action == "inject" and first.reason_code == "basic_memory_nudge"
    assert second.action == "allow"
