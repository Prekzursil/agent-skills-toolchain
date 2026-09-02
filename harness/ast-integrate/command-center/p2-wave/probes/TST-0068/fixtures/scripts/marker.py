#!/usr/bin/env python3
"""TST-0068 live marker (explicit python3, not a bare .sh case)."""
import sys

tag = sys.argv[1] if len(sys.argv) > 1 else "ok"
print(f"TST-0068-MARKER:{tag}")
