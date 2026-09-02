#!/usr/bin/env python3
"""Stdio MCP-mount analogue for first-use activation timing.

Prints a ready line, reads one stdin line, replies, exits. Not a product MCP
server; it is the measured cold-start stand-in for an stdio mount on this box.
"""
from __future__ import annotations

import sys

sys.stdout.write("ready\n")
sys.stdout.flush()
sys.stdin.readline()
sys.stdout.write('{"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n')
sys.stdout.flush()
