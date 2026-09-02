"""pytest bootstrap for command-center/harness: make ``both_states`` importable.

The harness is consumed by ``sys.path.insert(0, "command-center/harness")``;
running ``pytest command-center/harness`` from the repo root needs the same
directory on the import path before ``test_both_states`` is collected.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
