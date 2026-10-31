#!/usr/bin/env python3
# RES-0009 exit-2 hook: reads the verbatim stdin payload, emits the recorded
# stderr marker on stderr, exits 2 (blocking error for the events where the
# published table honors exit 2).
import sys

MARKER = "RES-0009-BLOCK-STDERR"

if __name__ == "__main__":
    payload = sys.stdin.read()
    sys.stderr.write(MARKER + chr(10))
    sys.exit(2)
