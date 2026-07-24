"""Pytest glue for the detector self-test gate (opt-in).

Puts this directory on ``sys.path`` so ``import detector_self_test`` resolves
from any collected test module, and re-exports the ``pytest_generate_tests``
hook so pytest emits one both-states test per discovered detector.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from detector_self_test import pytest_generate_tests  # noqa: E402  — sys.path is set just above

__all__ = ["pytest_generate_tests"]
