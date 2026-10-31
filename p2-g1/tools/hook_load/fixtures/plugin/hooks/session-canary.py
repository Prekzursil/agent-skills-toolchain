"""IMP-0460 load-marker fixture hook: session-canary."""
import json
import sys

print(json.dumps({
    "hook-load-marker": "session-canary",
    "pid": None,
    "argv": sys.argv[1:],
}))
