"""Tests for the routing-hook intent-detection LOGIC (WU-1#1).

PURE function/regex classifier (NOT the live settings.json registration). It
decides whether a prompt is biomedical-data intent and whether to emit the
'query find_tools FIRST' additionalContext, given suppression state (TU used
in-session / within N turns), a repeat cap, and a one-time hint. It MUST NOT
emit updatedInput and MUST fail-open.
"""

from wearables.route_prompt import (
    FIND_TOOLS_HINT,
    ONE_TIME_HINT,
    RouteState,
    is_biomedical_intent,
    route_decision,
)


# --- intent classifier ------------------------------------------------------


def test_biomedical_intent_positive_examples():
    for prompt in (
        "What is the Ki of baclofen at the GABA-B receptor?",
        "pull IC50 data for this compound from ChEMBL",
        "find binding affinity for the GABAB1/2 heterodimer",
        "look up the pIC50 and EC50 for phenibut",
        "search PubChem for this InChIKey",
        "what does BindingDB say about this inhibitor's Kd",
    ):
        assert is_biomedical_intent(prompt), prompt


def test_biomedical_intent_negative_examples():
    for prompt in (
        "refactor this python module for me",
        "what's the weather in Paris",
        "write a haiku about the ocean",
        "fix the failing CI build",
    ):
        assert not is_biomedical_intent(prompt), prompt


def test_intent_is_case_insensitive():
    assert is_biomedical_intent("KI OF BACLOFEN AT GABA-B")


def test_intent_handles_non_string_failopen():
    assert is_biomedical_intent(None) is False
    assert is_biomedical_intent(123) is False


def test_intent_empty_string_is_false():
    assert is_biomedical_intent("") is False


# --- route_decision: emit / suppress / cap ---------------------------------


def test_emits_hint_on_biomedical_intent_fresh_state():
    decision = route_decision("Ki of baclofen at GABA-B", RouteState())
    assert decision.emit is True
    assert FIND_TOOLS_HINT in decision.additional_context
    # one-time hint included on first emission
    assert ONE_TIME_HINT in decision.additional_context
    # routing NEVER rewrites input
    assert decision.updated_input is None


def test_no_emit_for_non_biomedical_prompt():
    decision = route_decision("refactor this module", RouteState())
    assert decision.emit is False
    assert decision.additional_context == ""
    assert decision.updated_input is None


def test_suppressed_when_tu_used_in_session():
    state = RouteState(tu_used_in_session=True)
    decision = route_decision("Ki of baclofen", state)
    assert decision.emit is False


def test_suppressed_within_n_turns_since_tu():
    state = RouteState(turns_since_tu=1, suppress_within_turns=3)
    assert route_decision("Ki of baclofen", state).emit is False
    # exactly at the window edge -> still suppressed
    state_edge = RouteState(turns_since_tu=3, suppress_within_turns=3)
    assert route_decision("Ki of baclofen", state_edge).emit is False
    # beyond the window -> emits again
    state_past = RouteState(turns_since_tu=4, suppress_within_turns=3)
    assert route_decision("Ki of baclofen", state_past).emit is True


def test_repeat_cap_enforced():
    state = RouteState(emit_count=2, max_repeats=2)
    assert route_decision("Ki of baclofen", state).emit is False
    state_under = RouteState(emit_count=1, max_repeats=2)
    assert route_decision("Ki of baclofen", state_under).emit is True


def test_one_time_hint_only_on_first_emission():
    first = route_decision("Ki of baclofen", RouteState(emit_count=0))
    assert ONE_TIME_HINT in first.additional_context
    later = route_decision("Ki of baclofen", RouteState(emit_count=1, max_repeats=5))
    assert later.emit is True
    assert ONE_TIME_HINT not in later.additional_context


def test_route_never_emits_updated_input_even_when_emitting():
    decision = route_decision("Ki of baclofen", RouteState())
    assert decision.updated_input is None


def test_route_failopen_on_bad_state():
    # A non-RouteState (malformed) must fail-open: no emit, no raise.
    decision = route_decision("Ki of baclofen", object())
    assert decision.emit is False
    assert decision.additional_context == ""
    assert decision.updated_input is None


def test_route_failopen_on_bad_prompt():
    decision = route_decision(None, RouteState())
    assert decision.emit is False


def test_route_failopen_when_state_attr_raises():
    # A RouteState whose suppression fields raise mid-decision must fail-open
    # (exercises the except Exception path), not propagate.
    class ExplodingState(RouteState):
        def __init__(self):  # bypass dataclass field init
            pass

        @property
        def tu_used_in_session(self):  # type: ignore[override]
            raise RuntimeError("boom")

    decision = route_decision("Ki of baclofen", ExplodingState())
    assert decision.emit is False
    assert decision.additional_context == ""
    assert decision.updated_input is None
