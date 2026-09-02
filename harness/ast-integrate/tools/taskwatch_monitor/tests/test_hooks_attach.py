"""Unit tests for hooks.attach — the pure auto-attach decision layer.

Covers every branch of the kill-switch / 60s-threshold / whitelist gate
(:func:`should_attach`) and the dedup layer on top (:func:`decide`), plus the
small value helpers.
"""

from __future__ import annotations

from hooks.attach import (
    ATTACH_THRESHOLD_S,
    DEFAULT_WHITELIST,
    AttachDecision,
    AttachOp,
    decide,
    dedup_key,
    should_attach,
)

WL = DEFAULT_WHITELIST


def _op(
    op_id: str = "op1",
    op_kind: str = "bash-background",
    elapsed_s: float = 120.0,
    log_path: str = "/logs/run.log",
) -> AttachOp:
    return AttachOp(
        op_id=op_id, op_kind=op_kind, elapsed_s=elapsed_s, log_path=log_path
    )


# --------------------------------------------------------------------------- should_attach
def test_should_attach_green_path():
    assert should_attach("longrun", 120.0, WL, False) is True


def test_should_attach_killswitch_wins_over_everything():
    # Whitelisted + past threshold, but the kill-switch hard-disables.
    assert should_attach("longrun", 9_999.0, WL, True) is False


def test_should_attach_below_threshold():
    assert should_attach("longrun", ATTACH_THRESHOLD_S - 1, WL, False) is False


def test_should_attach_exactly_at_threshold_attaches():
    # >= threshold, not <, so the boundary attaches.
    assert should_attach("longrun", ATTACH_THRESHOLD_S, WL, False) is True


def test_should_attach_not_whitelisted():
    assert should_attach("foreground-read", 120.0, WL, False) is False


def test_should_attach_custom_threshold():
    assert should_attach("longrun", 30.0, WL, False, threshold_s=10.0) is True
    assert should_attach("longrun", 5.0, WL, False, threshold_s=10.0) is False


# --------------------------------------------------------------------------- dedup_key
def test_dedup_key_combines_kind_and_id():
    assert dedup_key(_op(op_id="abc", op_kind="longrun")) == "longrun:abc"


# --------------------------------------------------------------------------- decide
def test_decide_attaches_on_green_path():
    verdict = decide(_op())
    assert verdict == AttachDecision(
        attach=True, reason="attach", key="bash-background:op1"
    )


def test_decide_killswitch():
    verdict = decide(_op(), killswitch=True)
    assert verdict.attach is False and verdict.reason == "killswitch"


def test_decide_below_threshold():
    verdict = decide(_op(elapsed_s=10.0))
    assert verdict.attach is False and verdict.reason == "below-threshold"


def test_decide_not_whitelisted():
    verdict = decide(_op(op_kind="editor-save"))
    assert verdict.attach is False and verdict.reason == "not-whitelisted"


def test_decide_duplicate_is_rejected():
    op = _op()
    verdict = decide(op, seen={dedup_key(op)})
    assert verdict.attach is False and verdict.reason == "duplicate"


def test_decide_custom_whitelist():
    verdict = decide(_op(op_kind="my-op"), whitelist=frozenset({"my-op"}))
    assert verdict.attach is True


def test_attach_decision_to_dict():
    verdict = AttachDecision(attach=True, reason="attach", key="k")
    assert verdict.to_dict() == {"attach": True, "reason": "attach", "key": "k"}
