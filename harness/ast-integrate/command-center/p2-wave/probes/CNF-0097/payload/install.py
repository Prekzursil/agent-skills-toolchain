#!/usr/bin/env python3
"""Install the published harness plugin. Stdlib only. pathlib joins only."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def posix_dest(root: Path, rel_posix: str) -> Path:
    parts = [p for p in rel_posix.split("/") if p and p != "."]
    dest = root
    for part in parts:
        dest = dest / part
    return dest


def copy_tree(src: Path, dst: Path) -> list[str]:
    copied: list[str] = []
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src).as_posix()
        target = posix_dest(dst, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        copied.append(rel)
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="Install published harness plugin")
    parser.add_argument("--prefix", required=True, help="install prefix (posix path)")
    args = parser.parse_args()
    artifact_root = Path(__file__).resolve().parent
    plugin_src = artifact_root / "plugin"
    if not (plugin_src / "plugin.json").is_file():
        print("FAILED:install plugin.json missing from published artifact", file=sys.stderr)
        return 2
    prefix = Path(args.prefix)
    prefix.mkdir(parents=True, exist_ok=True)
    copied = copy_tree(plugin_src, prefix)
    receipt = {
        "copied_files": copied,
        "file_count": len(copied),
        "prefix": prefix.as_posix(),
        "source": artifact_root.as_posix(),
    }
    (prefix / "install-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"installed files={len(copied)} prefix={prefix.as_posix()}")
    print("SUCCESS:install")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
