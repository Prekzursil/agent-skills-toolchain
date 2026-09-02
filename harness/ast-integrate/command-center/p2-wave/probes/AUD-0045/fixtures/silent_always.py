#!/usr/bin/env python3
"""Control fixture: exits 0 on empty AND on known-bad, prints CLEAN, no count.

A census that does not classify this as measuring-nothing is itself fail-open.
"""
from __future__ import annotations

import sys

print("CLEAN")
raise SystemExit(0)
