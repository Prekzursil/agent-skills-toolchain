#!/usr/bin/env python3
from hashlib import sha256
from pathlib import Path
p = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\ovh-monitor\g1-shards\shard-02.remaining.txt")
raw = p.read_bytes()
print("bytes", len(raw))
print("crlf", b"\r\n" in raw)
print("lf_only", raw.count(b"\n"), "nlines", raw.count(b"\n"))
print("sha256", sha256(raw).hexdigest())
print("ids", [ln for ln in raw.decode("utf-8").splitlines() if ln.strip()])
