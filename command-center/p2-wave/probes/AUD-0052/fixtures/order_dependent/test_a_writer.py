"""Ground-truth order-dependent fixture, half A: writes shared state.

Deliberately engineered: passes trivially, and its ONLY effect is to leave a
side-effect file behind for test_b_reader.py::test_b_requires_writer_flag to read.
Paired with test_b_reader.py this is the known-broken control probe1 must catch --
if the shuffle plugin never actually reorders, test_b always sees the flag (because
declaration order always runs A before B) and the census would silently miss a real
order-dependent test.
"""

from __future__ import annotations

from pathlib import Path

STATE = Path(__file__).parent / "_shared_state.tmp"


def test_a_writes_flag() -> None:
    STATE.write_text("written-by-test-a\n", encoding="utf-8")
    assert True
