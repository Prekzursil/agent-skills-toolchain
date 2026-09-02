#!/usr/bin/env python3
"""Slow hook for timeout control."""
from __future__ import annotations

import sys
import time

sys.stdin.buffer.read()
time.sleep(30)
sys.exit(0)
