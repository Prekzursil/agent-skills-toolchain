"""AUD-0056 ground-truth slow fixture.

A deliberately slow tiny test that MUST appear in the slowest set when the
runtime profile is measured. If --durations / external wall-clock ranking
fails to surface this node, the instrument is broken (false baseline), not
evidence that the suite is uniformly fast.
"""

from __future__ import annotations

import time

# 0.80s is well above the natural slowest call (~0.5s) observed on this
# command-center/ slice in an uncontended cloud runner, so the control is
# not contention-dependent for detection.
SLOW_SECONDS = 0.80


def test_aud0056_deliberately_slow_control() -> None:
    time.sleep(SLOW_SECONDS)
