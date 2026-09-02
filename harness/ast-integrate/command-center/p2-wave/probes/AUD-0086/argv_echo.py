#!/usr/bin/env python3
"""Print received argv[1:] as JSON. Used by the AUD-0086 round-trip probe."""
import json
import sys

print(json.dumps(sys.argv[1:], ensure_ascii=False))
