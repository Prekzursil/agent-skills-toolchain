"""Ground-truth flaky fixture: nondeterministic regardless of collection order.

Uses the OS entropy pool (no fixed seed), so its outcome varies run-to-run even
under the byte-identical declaration order probe2 always uses. This is the
control for probe2: if five identical-order repeats always show 100% agreement on
this test too, the repeat harness itself is not actually re-executing independent
process runs (e.g. a cached result), and that failure mode must be caught rather
than silently reported as "no flake found".
"""

from __future__ import annotations

import os


def test_flaky_probability() -> None:
    # ~40% intrinsic failure rate, reseeded from OS entropy on every process start
    # (no explicit seed -- that is the point: genuinely independent per run).
    draw = int.from_bytes(os.urandom(2), "big") / 65535.0
    assert draw > 0.40, f"flaky-ground-truth draw={draw:.4f}"
