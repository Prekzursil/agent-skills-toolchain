"""RegisterGateModule: re-entrancy, both-states control, shape, and wiring.

The re-entrancy block is FIRST on purpose. On 2026-08-08 `SensitiveArtifactModule`
ran on SubagentStop with no `stop_hook_active` guard and two trivial probes
("reply with one token, use no tools") cost 62,155 and 63,222 tokens with zero
tool uses. That bug was a MISSING BRANCH, so each branch is pinned individually
rather than covered incidentally.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from harness.models import HookEvent
from harness.modules import (
    GATE_CONTRACTS,
    MODULE_ORDER,
    TIER_HEURISTIC,
    RegisterGateModule,
    build_default_modules,
    resolve_mode,
)

REPO = Path(__file__).resolve().parents[3]
REAL_CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

MONITOR_PROMPT = (
    "let's finish the monitor cockpit and wire its CLI so the dashboard is reachable"
)
PROGRAM_B_PROMPT = "resume program B workflow_design and the skill lifecycle work"
VAGUE_HARNESS_PROMPT = "let's do some harness work today"
NEGATIVE_PROMPTS = (
    "what is the weather like in Bucharest today",
    "thanks, that looks good to me",
)


def event(
    prompt: str = "",
    *,
    name: str = "UserPromptSubmit",
    session: str = "session-1",
    trigger: str = "",
    agent_type: str = "",
) -> HookEvent:
    kwargs = {
        "schema_version": 1,
        "provider": "claude",
        "event": name,
        "session_id": session,
        "turn_id": "turn-1",
        "cwd": str(REPO),
        "permission_mode": "default",
        "prompt": prompt,
        "trigger": trigger,
    }
    evt = HookEvent(**kwargs)
    if agent_type:
        object.__setattr__(evt.agent, "id", agent_type)
    return evt


@pytest.fixture()
def gate(tmp_path: Path, monkeypatch) -> RegisterGateModule:
    """Advise mode so the verdict is observable; shadow would mask every inject."""
    monkeypatch.setenv("HARNESS_GATE_MODE__register_gate", "advise")
    monkeypatch.delenv("HARNESS_REGISTER", raising=False)
    return RegisterGateModule(state_root=tmp_path / "flags")


@pytest.fixture()
def catalog() -> dict:
    return json.loads(REAL_CATALOG.read_text(encoding="utf-8"))


def write_catalog(tmp_path: Path, catalog: dict) -> Path:
    path = tmp_path / "WORK-UNIT-CATALOG.json"
    path.write_text(json.dumps(catalog), encoding="utf-8", newline="\n")
    return path


def gate_on(tmp_path: Path, catalog: dict, monkeypatch) -> RegisterGateModule:
    monkeypatch.setenv("HARNESS_GATE_MODE__register_gate", "advise")
    return RegisterGateModule(
        state_root=tmp_path / "flags", catalog_path=write_catalog(tmp_path, catalog)
    )


def close_all(catalog: dict, program: str | None = None) -> dict:
    for item in catalog["items"]:
        if program is None or item.get("program") == program:
            item["disposition"] = "DONE-VERIFIED"
    return catalog


# ==========================================================================
# 1. RE-ENTRANCY -- write these first; the bug was a missing branch
# ==========================================================================


@pytest.mark.parametrize("name", ["Stop", "StopFailure", "SubagentStop"])
def test_never_runs_on_the_stop_family(gate, name):
    assert gate.run(event(MONITOR_PROMPT, name=name)).action == "allow"


def test_subagent_stop_with_stop_hook_active_is_allowed(gate):
    """Pinned explicitly even though the event check already covers it: the
    2026-08-08 defect was the ABSENCE of this branch, not a wrong condition."""
    result = gate.run(
        event(MONITOR_PROMPT, name="SubagentStop", trigger="stop_hook_active")
    )
    assert result.action == "allow"


@pytest.mark.parametrize("name", ["UserPromptSubmit", "SessionStart"])
def test_reentrant_trigger_is_allowed_on_accepted_events_too(gate, name):
    assert (
        gate.run(event(MONITOR_PROMPT, name=name, trigger="stop_hook_active")).action
        == "allow"
    )


def test_fixed_point_the_gate_does_not_match_its_own_output(gate):
    """Self-amplification: feed the gate's own injected text back as the next
    prompt. A keyword gate on UserPromptSubmit is uniquely able to hit this, and
    no existing harness test covers the case."""
    first = gate.run(event(MONITOR_PROMPT))
    assert first.action == "inject"
    injected = first.additional_context[0]
    echo = gate.run(event(injected, session="session-echo"))
    assert echo.action == "allow", injected


def test_fifty_identical_prompts_produce_exactly_one_injection(gate):
    """Loop bound. Per-item session cooldown must converge, not oscillate."""
    fires = [gate.run(event(MONITOR_PROMPT)).action for _ in range(50)]
    assert fires.count("inject") == 1
    assert fires[0] == "inject"


def test_a_new_session_gets_its_own_cooldown(gate):
    assert gate.run(event(MONITOR_PROMPT, session="s1")).action == "inject"
    assert gate.run(event(MONITOR_PROMPT, session="s1")).action == "allow"
    assert gate.run(event(MONITOR_PROMPT, session="s2")).action == "inject"


def test_a_subagent_is_never_nudged(gate):
    assert (
        gate.run(event(MONITOR_PROMPT, agent_type="workflow-subagent")).action
        == "allow"
    )


# ==========================================================================
# 2. BOTH-STATES CONTROL -- fires on stale, silent on clean
# ==========================================================================


def test_fires_on_a_stale_register_for_the_monitor_program(gate):
    result = gate.run(event(MONITOR_PROMPT))
    assert result.action == "inject"
    body = result.additional_context[0]
    assert "R-M01" in body


def test_fires_on_a_stale_register_for_program_b(gate):
    result = gate.run(event(PROGRAM_B_PROMPT))
    assert result.action == "inject"
    assert "R-B" in result.additional_context[0]


def test_fires_on_a_deliberately_vague_prompt_via_the_program_bonus(gate):
    result = gate.run(event(VAGUE_HARNESS_PROMPT))
    assert result.action == "inject"
    assert "R-H" in result.additional_context[0]


@pytest.mark.parametrize("prompt", NEGATIVE_PROMPTS)
def test_negative_controls_stay_silent_while_the_register_is_stale(gate, prompt):
    assert gate.run(event(prompt)).action == "allow"


def test_silent_on_a_fully_clean_register(tmp_path, catalog, monkeypatch):
    clean = gate_on(tmp_path, close_all(catalog), monkeypatch)
    for prompt in (
        MONITOR_PROMPT,
        PROGRAM_B_PROMPT,
        VAGUE_HARNESS_PROMPT,
        *NEGATIVE_PROMPTS,
    ):
        assert clean.run(event(prompt, session=prompt[:8])).action == "allow"
    assert clean.run(event(name="SessionStart")).action == "allow"


def test_silent_on_a_clean_partial_register(tmp_path, catalog, monkeypatch):
    """The sharp control. Closing ONLY the 19 MONITOR items must silence the
    monitor prompt while 50 items stay open -- proving the gate tracks THESE
    items rather than merely 'the catalog is non-empty'."""
    partial = gate_on(tmp_path, close_all(catalog, program="MONITOR"), monkeypatch)
    assert partial.run(event(MONITOR_PROMPT)).action == "allow"
    assert partial.run(event(PROGRAM_B_PROMPT, session="s-b")).action == "inject"


def test_a_deferred_item_stops_being_surfaced_until_its_date(
    tmp_path, catalog, monkeypatch
):
    for item in catalog["items"]:
        if item.get("program") == "MONITOR":
            item["defer"] = {"until": "2099-01-01T00:00:00+00:00", "reason": "parked"}
    deferred = gate_on(tmp_path, catalog, monkeypatch)
    assert deferred.run(event(MONITOR_PROMPT)).action == "allow"


def test_an_expired_deferral_returns_on_its_own(tmp_path, catalog, monkeypatch):
    for item in catalog["items"]:
        if item.get("program") == "MONITOR":
            item["defer"] = {"until": "2020-01-01T00:00:00+00:00", "reason": "parked"}
    expired = gate_on(tmp_path, catalog, monkeypatch)
    assert expired.run(event(MONITOR_PROMPT)).action == "inject"


def test_a_malformed_defer_date_does_not_hide_the_item(tmp_path, catalog, monkeypatch):
    for item in catalog["items"]:
        if item.get("program") == "MONITOR":
            item["defer"] = {"until": "not-a-date", "reason": "typo"}
    broken = gate_on(tmp_path, catalog, monkeypatch)
    assert broken.run(event(MONITOR_PROMPT)).action == "inject"


# ==========================================================================
# 3. SHAPE -- selectivity, cap, and the legal next move
# ==========================================================================


def test_a_huge_paste_matching_everything_stays_silent(gate, catalog):
    """Selectivity ceiling. A 20 KB paste legitimately contains almost every rare
    token in the catalog; surfacing 60 items would be noise, not a notice."""
    paste = " ".join(str(item["title"]) for item in catalog["items"])
    assert len(paste) > 8000
    assert gate.run(event(paste)).action == "allow"


def test_at_most_three_items_are_shown(gate, catalog):
    result = gate.run(event(MONITOR_PROMPT))
    shown = [
        line
        for line in result.additional_context[0].splitlines()
        if line.startswith("  R-")
    ]
    assert 1 <= len(shown) <= 3


def test_the_injection_always_leaves_a_legal_next_move(gate):
    """The other half of the 2026-08-08 bug: an advisory whose only satisfying
    action is policy-forbidden is a deadlock, so the model loops instead of
    stopping. Three moves, one of which is always available."""
    body = gate.run(event(MONITOR_PROMPT)).additional_context[0]
    assert "work it now" in body
    assert "close.py" in body
    assert "--defer" in body
    assert "NOTICE, not a task" in body


def test_the_injection_never_quotes_the_evidence_column(gate, catalog):
    """`evidence` holds long paths and credential-adjacent prose (R-B08 names a
    file of live tokens). It must never reach the terminal."""
    body = gate.run(event(MONITOR_PROMPT)).additional_context[0]
    for item in catalog["items"]:
        evidence = str(item.get("evidence", ""))
        if len(evidence) > 40:
            assert evidence not in body


def test_the_injection_is_short(gate):
    body = gate.run(event(MONITOR_PROMPT)).additional_context[0]
    assert len(body.splitlines()) <= 10


def test_the_injection_never_uses_coercive_words(gate):
    body = gate.run(event(MONITOR_PROMPT)).additional_context[0].lower()
    for word in ("must", "blocked", "before you continue"):
        assert word not in body


def test_session_start_emits_one_short_digest(gate):
    result = gate.run(event(name="SessionStart"))
    assert result.action == "inject"
    assert result.reason_code == "register_gate_digest"
    body = result.additional_context[0]
    assert "69 open" in body
    assert len(body.splitlines()) <= 3


# ==========================================================================
# 4. FAIL-OPEN -- a broken catalog is silence, never a crash
# ==========================================================================


@pytest.mark.parametrize(
    "payload", ["", "   ", "{not json", "[]", '{"items": "nope"}', '{"items": []}']
)
def test_a_broken_or_empty_catalog_is_silent(tmp_path, monkeypatch, payload):
    monkeypatch.setenv("HARNESS_GATE_MODE__register_gate", "advise")
    path = tmp_path / "WORK-UNIT-CATALOG.json"
    path.write_text(payload, encoding="utf-8")
    broken = RegisterGateModule(state_root=tmp_path / "flags", catalog_path=path)
    assert broken.run(event(MONITOR_PROMPT)).action == "allow"


def test_auto_discovery_finds_the_repo_catalog(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_GATE_MODE__register_gate", "advise")
    monkeypatch.delenv("HARNESS_REGISTER_CATALOG", raising=False)
    found = RegisterGateModule(state_root=tmp_path / "flags")
    assert found.run(event(MONITOR_PROMPT)).action == "inject"


def test_an_explicit_but_broken_path_does_NOT_fall_back_to_another_register(
    tmp_path, monkeypatch
):
    """A misconfiguration must be silence, not a silent read of a DIFFERENT
    register. Falling through would make the gate report on a catalog the
    operator did not name -- green-not-live in the other direction."""
    monkeypatch.setenv("HARNESS_GATE_MODE__register_gate", "advise")
    absent = RegisterGateModule(
        state_root=tmp_path / "flags", catalog_path=tmp_path / "nope.json"
    )
    assert absent.run(event(MONITOR_PROMPT)).action == "allow"


def test_a_garbage_row_is_skipped_not_crashed_on(tmp_path, catalog, monkeypatch):
    catalog["items"].append({"id": "R-", "title": ""})
    catalog["items"].append({"id": "R-X99"})
    catalog["items"].append("not even a dict")
    messy = gate_on(tmp_path, catalog, monkeypatch)
    assert messy.run(event(MONITOR_PROMPT)).action == "inject"


def test_an_unreadable_flag_store_does_not_break_the_gate(
    tmp_path, catalog, monkeypatch
):
    guarded = gate_on(tmp_path, catalog, monkeypatch)
    monkeypatch.setattr(
        guarded, "_flag_path", lambda evt: tmp_path / "no" / "such" / "dir" / "f.json"
    )
    assert guarded.run(event(MONITOR_PROMPT)).action == "inject"


def test_an_internal_error_fails_open(gate, monkeypatch):
    monkeypatch.setattr(
        gate, "_load_catalog", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    assert gate.run(event(MONITOR_PROMPT)).action == "allow"


def test_the_kill_switch_short_circuits_everything(gate, monkeypatch):
    monkeypatch.setenv("HARNESS_REGISTER", "off")
    assert gate.run(event(MONITOR_PROMPT)).action == "allow"
    assert gate.run(event(name="SessionStart")).action == "allow"


def test_an_empty_prompt_is_silent(gate):
    assert gate.run(event("")).action == "allow"
    assert gate.run(event("   ")).action == "allow"


# ==========================================================================
# 5. LADDER AND WIRING -- green-not-live is the defect this lane exists to catch
# ==========================================================================


def test_default_mode_is_shadow(monkeypatch):
    monkeypatch.delenv("HARNESS_GATE_MODE__register_gate", raising=False)
    assert resolve_mode("register_gate", tier=TIER_HEURISTIC) == "shadow"


def test_in_shadow_a_firing_verdict_is_swallowed_and_logged(tmp_path, monkeypatch):
    monkeypatch.delenv("HARNESS_GATE_MODE__register_gate", raising=False)
    monkeypatch.setenv("AGENT_HARNESS_STATE_ROOT", str(tmp_path / "state"))
    shadowed = RegisterGateModule(state_root=tmp_path / "flags")
    assert shadowed.run(event(MONITOR_PROMPT)).action == "allow"
    sink = list((tmp_path / "state" / "shadow").glob("shadow-*.jsonl"))
    assert sink, "shadow mode must leave an observation behind"
    records = [
        json.loads(line) for line in sink[0].read_text(encoding="utf-8").splitlines()
    ]
    assert any(rec["gate"] == "register_gate" for rec in records)


def test_a_forced_enforce_still_cannot_block(gate, monkeypatch):
    """The verdict is an inject in every mode, so the enforce rung is inert by
    construction and the gate cannot fail closed."""
    monkeypatch.setenv("HARNESS_GATE_MODE__register_gate", "enforce")
    assert gate.run(event(MONITOR_PROMPT)).action == "inject"


def test_off_mode_is_silent(gate, monkeypatch):
    monkeypatch.setenv("HARNESS_GATE_MODE__register_gate", "off")
    assert gate.run(event(MONITOR_PROMPT)).action == "allow"


def test_the_module_is_actually_wired(monkeypatch, tmp_path):
    """The check whose ABSENCE killed the prior art: `open-loops/trigger_match.py`
    is fully written, needs a `UserPromptSubmit` entry, and never got one. A gate
    that passes its own tests and is reachable by nothing is green-not-live."""
    assert "register_gate" in MODULE_ORDER
    assert "register_gate" in GATE_CONTRACTS
    names = [getattr(module, "name", "") for module in build_default_modules(tmp_path)]
    assert "register_gate" in names


def test_the_contract_records_a_measured_fire_rate():
    contract = GATE_CONTRACTS["register_gate"]
    assert contract["metric"] == "register_item_closed_after_fire"
    assert "MEASURED" in contract["fire_rate"]
    assert "3.16" in contract["fire_rate"]


def test_the_predicate_is_the_one_the_measurement_used(catalog):
    """`measure_rate.py` calls `would_fire` directly; if that entry point moved,
    the published rate would describe a gate that no longer exists."""
    items = [item for item in catalog["items"] if not item.get("disposition")]
    matched, programs = RegisterGateModule().would_fire(MONITOR_PROMPT, items)
    assert "R-M01" in matched
    assert "MONITOR" in programs
