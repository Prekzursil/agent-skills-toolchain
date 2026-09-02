#!/usr/bin/env python3
"""Executable check that errors: crash, no JSON, exit 2. Must become NOT-CHECKED."""
from __future__ import annotations

import sys

sys.stderr.write("TST-0274 planted probe crash: no asserted fact\n")
sys.exit(2)
