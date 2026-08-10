"""Pytest bootstrap: put the package dir on sys.path so `import suitefloor` resolves from tests/
with no install step (same shape as tools/command-center/conftest.py)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
