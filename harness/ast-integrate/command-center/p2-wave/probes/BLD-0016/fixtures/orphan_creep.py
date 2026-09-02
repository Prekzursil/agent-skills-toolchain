"""Orphan fixture that asserts something no requirement asked for (scope creep)."""


def test_unrelated_helper_speed_scope_creep():
    elapsed_ms = 0
    assert elapsed_ms < 5
