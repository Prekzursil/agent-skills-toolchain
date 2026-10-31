#!/usr/bin/env python3
"""Targeted rsync of shard-07 surfaces into ~/p2-g1. No bash $ vars."""
from __future__ import annotations

import subprocess
from pathlib import Path

SRC = Path("/mnt/c/Users/Prekzursil/source/ast-integrate")
DST = Path.home() / "p2-g1"
IDS = SRC / "command-center/p2-wave/ovh-monitor/g1-shards/shard-07.txt"


def rsync(src: str, dst: str, extra: list[str] | None = None) -> None:
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-a", "--exclude", "__pycache__", "--exclude", "*.pyc"]
    if extra:
        cmd.extend(extra)
    cmd.extend([src, dst])
    subprocess.run(cmd, check=True)


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    ids = [ln.strip() for ln in IDS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    for uid in ids:
        src = SRC / "command-center/p2-wave/probes" / uid
        if not src.is_dir():
            continue
        dst = DST / "command-center/p2-wave/probes" / uid
        dst.mkdir(parents=True, exist_ok=True)
        rsync(str(src) + "/", str(dst) + "/", ["--exclude", "deps"])
    print("PROBES-OK", len(ids))
    for rel in (
        "command-center/receipts",
        "command-center/adversarial",
        "command-center/audit",
        "command-center/wfa",
        "command-center/research",
        "command-center/schema",
        "command-center/p2-wave/seed-stage",
    ):
        src = SRC / rel
        if src.is_dir():
            dst = DST / rel
            dst.mkdir(parents=True, exist_ok=True)
            rsync(str(src) + "/", str(dst) + "/")
            print("OK", rel)
    rsync(
        str(SRC / "command-center/p2-wave/_measure_one_delivered.py"),
        str(DST / "command-center/p2-wave/_measure_one_delivered.py"),
    )
    print("RSYNC-SHARD07-OK")


if __name__ == "__main__":
    main()
