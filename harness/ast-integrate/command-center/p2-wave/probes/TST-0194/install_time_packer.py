#!/usr/bin/env python3
"""Install-time-only mutant packer (negative control for TST-0194).

Copies staging into a zip with ZERO build-time casefold check. A later
"install" pass may notice a collision, which is exactly the failure class
TST-0194 forbids: the user's case-insensitive filesystem is the detector.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def posix_rel(path: str) -> str:
    text = str(path).replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def load_manifest_paths(manifest: Path) -> list[str]:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if isinstance(data, list):
        entries = data
    else:
        entries = data.get("files") or data.get("paths") or []
    return [posix_rel(str(x)) for x in entries if str(x).strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    members = load_manifest_paths(args.manifest)
    # Deliberately no collision check. Missing files are skipped so a
    # declared-only colliding manifest still "builds".
    args.output.parent.mkdir(parents=True, exist_ok=True)
    packed = 0
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in members:
            src = args.staging / rel
            if not src.is_file():
                continue
            info = zipfile.ZipInfo(filename=rel, date_time=FIXED_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, src.read_bytes())
            packed += 1
    print(f"MUTANT_PACKED_AT_BUILD {args.output} entries={packed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
