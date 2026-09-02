#!/usr/bin/env python3
from pathlib import Path
p = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\ovh-monitor\g1-shards\_measure_shard08.sh")
data = p.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
p.write_bytes(data)
print("lf-ok", p, len(data))
