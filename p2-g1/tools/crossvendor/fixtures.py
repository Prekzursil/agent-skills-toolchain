"""Labelled byte-pair fixtures for the four divergence classes."""
from __future__ import annotations

from typing import Any

# Each case is a pair of byte strings plus a ground-truth class.
# IDENTICAL: equal bytes.
# AHEAD: ours has unique spans; theirs is a strict subset.
# BEHIND: theirs has unique spans; ours is a strict subset.
# DIVERGED: both sides hold unique content.


def labelled_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    identical = [
        (b"alpha\nbeta\n", b"alpha\nbeta\n"),
        (b"same-bytes-02", b"same-bytes-02"),
        (b"", b""),
        (b"utf8-\xc3\xa9", b"utf8-\xc3\xa9"),
        (b"line\nline\n", b"line\nline\n"),
    ]
    ahead = [
        (b"shared\nours-only-A\n", b"shared\n"),
        (b"keep\nplus-left-02", b"keep\n"),
        (b"base\nLEFT-UNIQUE-03\n", b"base\n"),
        (b"head\nours-span-04", b"head\n"),
        (b"common-token X ours-only-05", b"common-token X"),
    ]
    behind = [
        (b"shared\n", b"shared\ntheirs-only-A\n"),
        (b"keep\n", b"keep\nplus-right-02"),
        (b"base\n", b"base\nRIGHT-UNIQUE-03\n"),
        (b"head\n", b"head\ntheirs-span-04"),
        (b"common-token Y", b"common-token Y theirs-only-05"),
    ]
    diverged = [
        (b"ours-only-D1\nshared\n", b"shared\ntheirs-only-D1\n"),
        (b"left-unique-D2", b"right-unique-D2"),
        (b"AAA-left\ncommon", b"common\nBBB-right"),
        (b"span-L-04 extra", b"span-R-04 extra-other"),
        (b"opcode-L-05", b"opcode-R-05"),
    ]
    for i, (ours, theirs) in enumerate(identical, 1):
        cases.append({"id": f"ID-{i:02d}", "label": "IDENTICAL", "ours": ours, "theirs": theirs})
    for i, (ours, theirs) in enumerate(ahead, 1):
        cases.append({"id": f"AH-{i:02d}", "label": "AHEAD", "ours": ours, "theirs": theirs})
    for i, (ours, theirs) in enumerate(behind, 1):
        cases.append({"id": f"BH-{i:02d}", "label": "BEHIND", "ours": ours, "theirs": theirs})
    for i, (ours, theirs) in enumerate(diverged, 1):
        cases.append({"id": f"DV-{i:02d}", "label": "DIVERGED", "ours": ours, "theirs": theirs})
    return cases
