"""Both-states detector helpers used by ADV-0009 and related audits."""
from __future__ import annotations

from tools.test_support.both_states import (
    FIRES,
    SILENT,
    BothStatesError,
    assert_both_states,
    run_both_states,
)
from tools.test_support.selftest import (
    always_on_detector,
    discriminating_detector,
    run_selftest,
    silent_detector,
)

__all__ = [
    "FIRES",
    "SILENT",
    "BothStatesError",
    "always_on_detector",
    "assert_both_states",
    "discriminating_detector",
    "run_both_states",
    "run_selftest",
    "silent_detector",
]
