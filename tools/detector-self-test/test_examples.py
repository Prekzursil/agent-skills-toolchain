"""The plugin proof: every committed example must pass its own both-states self-test.

The ``detector_case`` parameter is supplied by ``pytest_generate_tests`` (re-exported in
``conftest.py``), which discovers the ``examples/`` root. This asserts each worked example
is correctly wired: it FIRES on its ``broken/`` fixture and is SILENT on its ``fixed/`` one.
A detector that is silent-in-both, firing-in-both, or inverted fails this gate.
"""

from __future__ import annotations

from detector_self_test import DetectorCase, Outcome, evaluate


def test_example_detector_passes_both_states(detector_case: DetectorCase) -> None:
    result = evaluate(detector_case)
    assert result.outcome is Outcome.PASS, result.message
