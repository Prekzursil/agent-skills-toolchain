"""Pytest bootstrap for the TG-2 mutation-gate.

Puts the gate module on ``sys.path`` (so ``import mutation_gate`` works from the
``tests/`` package without an install step) and registers the ``demo`` marker used
by the real-cosmic-ray integration tests.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "demo: real cosmic-ray end-to-end demo (slow; needs cosmic-ray installed)",
    )
