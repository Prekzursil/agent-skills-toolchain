#!/usr/bin/env python3
"""Deployed-copy mutant: writes a canary and exits 2. Must never be executed."""
from __future__ import annotations

import os
import sys
from pathlib import Path

canary = os.environ.get("IMP0404_DEPLOYED_CANARY")
if canary:
    Path(canary).write_text("DEPLOYED-MUTANT-RAN\n", encoding="utf-8")
sys.stderr.write("mutant deployed prompt-submit blocking\n")
sys.exit(2)
