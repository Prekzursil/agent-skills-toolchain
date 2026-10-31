"""Pytest bootstrap for the command-center backlog tooling.

Puts the package dir on ``sys.path`` so ``import catalog`` / ``import validate``
resolve from ``tests/`` with no install step (same shape as
``tools/mutation-gate/conftest.py``).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
