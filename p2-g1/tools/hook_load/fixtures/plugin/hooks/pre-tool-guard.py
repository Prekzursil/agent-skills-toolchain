"""IMP-0460 load-marker fixture hook: pre-tool-guard."""
import json
import sys

print(json.dumps({
    "hook-load-marker": "pre-tool-guard",
    "pid": None,
    "argv": sys.argv[1:],
}))
