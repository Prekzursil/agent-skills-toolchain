"""Non-gated helper. Default-argument mutant is intended to survive.

Tests only call scale_count with an explicit scale, so flipping SCALE_DEFAULT
does not turn the helper suite red. That survivor must show up in the
per-module table and must NOT fail the gated-module gate.
"""

from __future__ import annotations

SCALE_DEFAULT = 1  # tst0119-site:default-arg


def scale_count(n: int, scale: int | None = None) -> int:
    if scale is None:
        scale = SCALE_DEFAULT
    return n * scale
