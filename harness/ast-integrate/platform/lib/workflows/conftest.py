"""Make ``import mechanisms`` / ``import bp3_testkit`` / ``import wfdsl`` resolve for these tests.

Mirrors wfdsl/conftest.py: ``platform/lib`` goes on sys.path so ``wfdsl`` resolves by its own
name, and ``platform/lib/workflows`` goes on too so the blueprint-local modules resolve without
turning ``platform`` into a real package (which would shadow the stdlib ``platform`` module).
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB_ROOT = HERE.parent

for entry in (str(LIB_ROOT), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)
