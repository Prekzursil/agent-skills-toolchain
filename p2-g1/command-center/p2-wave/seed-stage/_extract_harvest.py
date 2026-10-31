#!/usr/bin/env python3
"""Extract harvest tgz files locally, skip node_modules, no overwrite of existing probes dest."""
from __future__ import annotations

import tarfile
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "ovh-monitor" / "error-pull" / "harvest"
DST = Path(__file__).resolve().parent.parent / "ovh-monitor" / "error-pull" / "extracted"
SKIP = {"node_modules", "__pycache__"}
RESERVED = {"NUL", "CON", "PRN", "AUX", "COM1", "COM2", "LPT1", "LPT2"}


def ok_member(name: str) -> bool:
    parts = Path(name).parts
    if any(p in SKIP for p in parts):
        return False
    if any(p.upper().split(".")[0] in RESERVED for p in parts):
        return False
    return True


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    nfiles = 0
    for tgz in sorted(SRC.glob("*.tgz")):
        box = tgz.stem
        dest = DST / box
        dest.mkdir(parents=True, exist_ok=True)
        extracted = 0
        skipped = 0
        with tarfile.open(tgz, "r:gz") as tf:
            for m in tf.getmembers():
                if m.issym() or m.islnk():
                    skipped += 1
                    continue
                if not ok_member(m.name) or "\n" in m.name or "\r" in m.name:
                    skipped += 1
                    continue
                try:
                    tf.extract(m, dest, filter="fully_trusted")
                    extracted += 1
                except (OSError, tarfile.TarError, ValueError):
                    skipped += 1
        nfiles += extracted
        print(f"{box:10s} extracted={extracted} skipped={skipped} -> {dest}", flush=True)
    print("TOTAL_MEMBERS", nfiles)


if __name__ == "__main__":
    main()
