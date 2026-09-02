#!/usr/bin/env python3
"""Parent-directory trap: must never run for a child project without its own file."""
print("TST0338-PARENT-TRAP-MARKER")
raise SystemExit(0)
