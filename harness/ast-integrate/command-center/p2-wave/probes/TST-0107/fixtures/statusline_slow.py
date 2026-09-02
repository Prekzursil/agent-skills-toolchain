#!/usr/bin/env python3
"""Slow render used to prove CANCELLED (timeout kills in-flight work)."""
from __future__ import annotations

import sys
import time

time.sleep(2.0)
print("should-not-print")
raise SystemExit(0)
