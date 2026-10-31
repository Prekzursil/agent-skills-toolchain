#!/usr/bin/env python3
"""Probe-local child: print the argv it received as JSON (exact strings)."""
from __future__ import annotations

import json
import sys

if __name__ == "__main__":
    sys.stdout.write(json.dumps({"argv": sys.argv[1:]}))
