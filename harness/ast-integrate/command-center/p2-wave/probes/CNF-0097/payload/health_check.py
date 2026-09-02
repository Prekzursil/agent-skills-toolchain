#!/usr/bin/env python3
"""Health-check the installed prefix. Stdlib only. pathlib joins only."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def posix_dest(root: Path, rel_posix: str) -> Path:
    parts = [p for p in rel_posix.split("/") if p and p != "."]
    dest = root
    for part in parts:
        dest = dest / part
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="Health-check installed harness plugin")
    parser.add_argument("--prefix", required=True)
    args = parser.parse_args()
    prefix = Path(args.prefix)
    manifest_path = prefix / "plugin.json"
    if not manifest_path.is_file():
        print("FAILED:health plugin.json missing", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing: list[str] = []
    for key in ("hooks", "skills", "rules"):
        for rel in manifest.get(key) or []:
            if not posix_dest(prefix, str(rel)).is_file():
                missing.append(str(rel))
    if missing:
        print(f"FAILED:health missing declared files {missing}", file=sys.stderr)
        return 2
    backslash_paths = [
        p.relative_to(prefix).as_posix()
        for p in prefix.rglob("*")
        if p.is_file() and "\\" in p.relative_to(prefix).as_posix()
    ]
    if backslash_paths:
        print(f"FAILED:health windows-separator in installed paths {backslash_paths}", file=sys.stderr)
        return 2
    hook = posix_dest(prefix, "hooks/pre-tool.py")
    if hook.is_file():
        env = os.environ.copy()
        env["HARNESS_PREFIX"] = prefix.as_posix()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [sys.executable, "-B", str(hook)],
            cwd=str(prefix),
            env=env,
            capture_output=True,
            text=True,
        )
        side = prefix / "hook-side-effect.json"
        if proc.returncode != 0 or not side.is_file():
            print(
                f"FAILED:health hook-fire rc={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}",
                file=sys.stderr,
            )
            return 2
        print(f"hook-fired {side.as_posix()}")
    print(f"healthy prefix={prefix.as_posix()} name={manifest.get('name')} version={manifest.get('version')}")
    print("SUCCESS:health-check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
