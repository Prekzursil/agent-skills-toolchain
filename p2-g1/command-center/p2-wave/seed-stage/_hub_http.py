#!/usr/bin/env python3
"""Start threaded HTTP on hub for tree fan-out."""
from __future__ import annotations

import subprocess
from pathlib import Path

KEY = Path.home() / ".ssh" / "id_ed25519"
HUB = "176.31.201.16"
REMOTE = r"""
sudo pkill -f 'http.server 8000' || true
sudo pkill -f THREAD-HTTP || true
cat > /tmp/thread_http.py << 'PY'
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os
os.chdir("/tmp")
print("THREAD-HTTP-READY", flush=True)
ThreadingHTTPServer(("0.0.0.0", 8000), SimpleHTTPRequestHandler).serve_forever()
PY
nohup python3 /tmp/thread_http.py >/tmp/http-seed.log 2>&1 </dev/null &
sleep 1
ss -ltn | grep 8000 || echo NO-PORT
tail -n 3 /tmp/http-seed.log
"""


def main() -> None:
    p = subprocess.run(
        [
            "ssh",
            "-i",
            str(KEY),
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=12",
            "-o",
            "StrictHostKeyChecking=accept-new",
            f"ubuntu@{HUB}",
            REMOTE,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    print(p.stdout)
    print(p.stderr)
    print("rc", p.returncode)


if __name__ == "__main__":
    main()
