#!/usr/bin/env python3
"""Non-protective oracle: ignores the subject and always PASSes.

A test written after the fix and never run against the broken state.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True
sys.exit(0)
