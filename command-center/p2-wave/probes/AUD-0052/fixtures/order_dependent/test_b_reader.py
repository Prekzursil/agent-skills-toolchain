"""Ground-truth order-dependent fixture, half B: requires the flag from half A.

FAILS whenever this test's collection position lands before
test_a_writer.py::test_a_writes_flag in the shuffled run -- which is exactly the
"passes in declaration order, fails under a shuffled order" shape AUD-0052's
question_or_target names. In declaration order (probe2, no shuffle) A always runs
first, so this test always passes there; it is only the shuffle in probe1 that can
expose it, which is the point of the fixture.
"""

from __future__ import annotations

from pathlib import Path

STATE = Path(__file__).parent / "_shared_state.tmp"


def test_b_requires_writer_flag() -> None:
    assert STATE.exists(), "order-dependent: test_a_writer must run first"
    assert STATE.read_text(encoding="utf-8") == "written-by-test-a\n"
