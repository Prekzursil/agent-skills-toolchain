#!/usr/bin/env python3
# REQUIRES: environment variable CNF0016_TRIGGER=1
"""Planted P0: only fails when CNF0016_TRIGGER=1. Recipe that omits the env var is insufficient."""
from __future__ import annotations

import os
import sys

if os.environ.get("CNF0016_TRIGGER") == "1":
    print("TRIGGERED:env-bug", flush=True)
    sys.exit(1)
print("OK:no-trigger", flush=True)
sys.exit(0)
