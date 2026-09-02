#!/usr/bin/env python3
"""Child: echo observed argv as JSON."""
from __future__ import annotations

import json
import sys

print(json.dumps({"argv": sys.argv[1:]}, separators=(",", ":")))
