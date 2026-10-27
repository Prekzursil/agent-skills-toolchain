import subprocess, sys, tempfile, os
from pathlib import Path

td = tempfile.mkdtemp(prefix="stdin-repro-")
sp = Path(td) / "t.sh"
sp.write_bytes(b"#!/bin/sh\necho repro-ok\n")
mode = sys.argv[1] if len(sys.argv) > 1 else "inherit"
kw = dict(capture_output=True, timeout=10, cwd=td)
if mode == "devnull":
    kw["stdin"] = subprocess.DEVNULL
try:
    p = subprocess.run(["bash", "t.sh"], **kw)
    print("rc:", p.returncode, "out:", p.stdout, "err:", p.stderr)
except subprocess.TimeoutExpired:
    print("TIMEOUT under mode", mode)
