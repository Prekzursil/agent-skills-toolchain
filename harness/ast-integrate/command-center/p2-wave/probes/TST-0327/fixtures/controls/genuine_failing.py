#!/usr/bin/env python3
"""Known-broken negative control for TST-0327: must FAIL when executed."""
import sys

print("TST-0327-control genuine_failing FIRE")
raise SystemExit(1)
