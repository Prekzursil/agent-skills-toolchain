#!/usr/bin/env python3
"""Diagnose exactly WHY four gates fail on Linux.  Run inside a full clone on POSIX."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))


def blob(rev: str, path: str) -> str:
    return subprocess.run(
        ["git", "show", f"{rev}:{path}"], cwd=REPO, capture_output=True, text=True
    ).stdout


def main() -> int:
    print(f"== host: {sys.platform}  py {sys.version.split()[0]} ==")

    rows = json.loads(blob("HEAD", "command-center/mcp-audit/disposition.json"))["rows"]
    srcs = {r["name"]: (r.get("source_file") or "") for r in rows}
    not_abs = [n for n, s in srcs.items() if s and not pathlib.Path(s).is_absolute()]
    not_exists = [
        n
        for n, s in srcs.items()
        if s and pathlib.Path(s).is_absolute() and not pathlib.Path(s).exists()
    ]
    print(f"  rows={len(rows)}  distinct source_file={len(set(srcs.values()))}")
    print(
        f"  pathlib.Path(src).is_absolute() FALSE for {len(not_abs)}/{len(rows)} rows"
    )
    print(f"  absolute-but-missing-on-disk    for {len(not_exists)}/{len(rows)} rows")
    sample = sorted(set(srcs.values()))[0]
    print(f"  sample={sample!r}")
    print(
        f"    PureWindowsPath.is_absolute() = {pathlib.PureWindowsPath(sample).is_absolute()}"
    )
    print(
        f"    PurePosixPath.is_absolute()   = {pathlib.PurePosixPath(sample).is_absolute()}"
    )

    print("\n== probe_capability control, state by state ==")
    import probe_capability as pc  # noqa: E402

    ok, results = pc.run_control()
    for r in results:
        print(f"  {r}")
    print(f"  run_control -> {ok}")
    print(f"  RESOLVE_SHIMS={getattr(pc, 'RESOLVE_SHIMS', '<absent>')}")

    print("SUCCESS:i2-diag-posix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
