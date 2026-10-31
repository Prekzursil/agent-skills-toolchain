#!/usr/bin/env python3
"""TST-0339 mutation helper: apply one default-value mutation to a copy.

Never mutates the committed fixtures; operates only on the scratch copy.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def apply(src: Path, dst: Path, old: str, new: str) -> dict:
    text = src.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        return {"ok": False, "reason": "expected exactly 1 occurrence, found %d" % n}
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text.replace(old, new), encoding="utf-8", newline="")
    return {"ok": True, "file": dst.as_posix(), "replaced": old, "with": new}


def run_suite(dst_dir: Path, test_file: str = "test_product.py") -> dict:
    proc = subprocess.run(
        [sys.executable, "-B", test_file],
        cwd=str(dst_dir), capture_output=True, text=True, timeout=300,
        env={"PYTHONDONTWRITEBYTECODE": "1",
             "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
             "PATH": os.environ.get("PATH", "")},
    )
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()[-6:]
    return {"exit_code": proc.returncode, "tail": tail}


if __name__ == "__main__":
    args = json.loads(sys.argv[1])
    print(json.dumps(apply(Path(args["src"]), Path(args["dst"]), args["old"], args["new"])))
