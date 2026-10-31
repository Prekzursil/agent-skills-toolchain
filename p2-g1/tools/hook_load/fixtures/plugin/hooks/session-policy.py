"""IMP-0460 load-marker fixture hook: session-policy."""
import json
import sys

print(json.dumps({
    "hook-load-marker": "session-policy",
    "pid": None,
    "argv": sys.argv[1:],
}))
