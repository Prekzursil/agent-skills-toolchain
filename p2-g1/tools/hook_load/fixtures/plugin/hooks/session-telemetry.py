"""IMP-0460 load-marker fixture hook: session-telemetry."""
import json
import sys

print(json.dumps({
    "hook-load-marker": "session-telemetry",
    "pid": None,
    "argv": sys.argv[1:],
}))
