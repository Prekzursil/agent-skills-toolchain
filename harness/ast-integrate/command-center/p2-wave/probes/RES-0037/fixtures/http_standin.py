#!/usr/bin/env python3
"""Long-lived HTTP MCP stand-in: one listening TCP socket, identity argv[1]."""
from __future__ import annotations

import socket
import sys
import time


def main() -> int:
    if len(sys.argv) < 2:
        print("FAILED:http-standin missing token", file=sys.stderr)
        return 2
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    port = srv.getsockname()[1]
    sys.stdout.write(f"PORT={port}\n")
    sys.stdout.flush()
    try:
        while True:
            time.sleep(0.25)
    finally:
        srv.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
