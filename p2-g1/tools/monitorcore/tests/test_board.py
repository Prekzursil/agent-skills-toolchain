"""Tests for ``monitorcore.board`` — the pure fixed-size frame-assembly substrate
(WU0), 100% line+branch.
"""

from __future__ import annotations

import pytest

from monitorcore.board import assemble_frame, clip_cell


@pytest.mark.parametrize(
    ("text", "cols", "expected"),
    [
        ("abcde", 0, ""),  # non-positive width
        ("abcde", -2, ""),  # negative width
        ("abcde", 3, "abc"),  # clip
        ("abc", 3, "abc"),  # exact width — no pad, no clip
        ("ab", 5, "ab   "),  # pad
        ("", 4, "    "),  # blank cell
    ],
)
def test_clip_cell(text: str, cols: int, expected: str) -> None:
    assert clip_cell(text, cols) == expected


def test_assemble_frame_zero_height_is_empty() -> None:
    assert assemble_frame(["a", "b"], 4, 0) == ()


def test_assemble_frame_drops_rows_beyond_height() -> None:
    assert assemble_frame(["one", "two", "three"], 3, 2) == ("one", "two")


def test_assemble_frame_pads_short_frame_with_blank_lines() -> None:
    assert assemble_frame(["hi"], 4, 3) == ("hi  ", "    ", "    ")


def test_assemble_frame_clips_and_pads_each_row_to_width() -> None:
    assert assemble_frame(["toolong", "x"], 4, 2) == ("tool", "x   ")
