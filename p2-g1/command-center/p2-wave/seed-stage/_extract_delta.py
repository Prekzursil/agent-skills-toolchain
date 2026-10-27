#!/usr/bin/env python3
"""Extract harvest-delta into local probes/ (overwrite) + per-box receipts."""
from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

WAVE = Path(__file__).resolve().parent.parent
SRC = WAVE / "ovh-monitor" / "error-pull" / "harvest-delta"
DST_BOX = WAVE / "ovh-monitor" / "error-pull" / "extracted-delta"
PROBES = WAVE / "probes"
SKIP = {"node_modules", "__pycache__"}
RESERVED = {"NUL", "CON", "PRN", "AUX", "COM1", "COM2", "LPT1", "LPT2"}


def ok_member(name: str) -> bool:
    parts = Path(name).parts
    if any(p in SKIP for p in parts):
        return False
    if any(p.upper().split(".")[0] in RESERVED for p in parts):
        return False
    if "\n" in name or "\r" in name:
        return False
    return True


def main() -> None:
    DST_BOX.mkdir(parents=True, exist_ok=True)
    copied = 0
    for tgz in sorted(SRC.glob("*.tgz")):
        box = tgz.stem
        dest = DST_BOX / box
        dest.mkdir(parents=True, exist_ok=True)
        extracted = skipped = 0
        with tarfile.open(tgz, "r:gz") as tf:
            for m in tf.getmembers():
                if m.issym() or m.islnk() or not ok_member(m.name):
                    skipped += 1
                    continue
                try:
                    tf.extract(m, dest, filter="fully_trusted")
                    extracted += 1
                except (OSError, tarfile.TarError, ValueError):
                    skipped += 1
        src_probes = dest / "probes"
        n = 0
        if src_probes.is_dir():
            for d in src_probes.iterdir():
                if not d.is_dir():
                    continue
                target = PROBES / d.name
                shutil.copytree(d, target, dirs_exist_ok=True)
                n += 1
        copied += n
        print(f"{box:10s} extracted={extracted} skipped={skipped} probe_dirs={n}", flush=True)
    print("PROBE_DIRS_COPIED", copied)


if __name__ == "__main__":
    main()
