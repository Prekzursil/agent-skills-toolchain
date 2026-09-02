#!/usr/bin/env python3
"""Blocking-error hook: stderr marker, exit 2."""
from __future__ import annotations

import sys

sys.stdin.buffer.read()
sys.stderr.write("RES-0009-BLOCK-STDERR\n")
sys.exit(2)
