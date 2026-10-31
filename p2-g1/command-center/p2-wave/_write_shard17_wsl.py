from pathlib import Path

p = Path(__file__).with_name("_g1_shard17_wsl.sh")
content = """#!/usr/bin/env bash
set -euo pipefail
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$AST_INTEGRATE_ROOT"
python3 -B command-center/p2-wave/_g1_shard17_run.py "$@"
"""
p.write_bytes(content.encode("utf-8").replace(b"\r\n", b"\n"))
print("wrote", p, "crlf", b"\r\n" in p.read_bytes())
