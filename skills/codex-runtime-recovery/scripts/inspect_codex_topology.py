#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

DEFAULT_NAMES = [".codex", ".codex-vscode", ".codex-vscode-consult"]


def count_sessions(root: Path) -> int:
    sessions = root / "sessions"
    if not sessions.exists():
        return 0
    return sum(1 for _ in sessions.rglob("rollout-*.jsonl"))


def inspect_root(root: Path) -> dict:
    data = {
        "path": str(root),
        "exists": root.exists(),
        "is_symlink": root.is_symlink(),
    }
    if not root.exists():
        return data
    data.update(
        {
            "auth_json": (root / "auth.json").exists(),
            "config_toml": (root / "config.toml").exists(),
            "sessions": count_sessions(root),
            "state_files": sorted(p.name for p in root.glob("state_5.sqlite*")),
            "migration_conflicts": (root / "migration_conflicts").exists(),
            "memories": (root / "memories").exists(),
        }
    )
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect likely Codex roots without mutating them.")
    parser.add_argument("--home", default=str(Path.home()), help="Home directory used to build default roots.")
    parser.add_argument("--root", action="append", default=[], help="Explicit Codex root to inspect. Repeatable.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()

    home = Path(args.home).expanduser()
    roots = []
    for name in DEFAULT_NAMES:
        roots.append(home / name)
    for raw in args.root:
        roots.append(Path(raw).expanduser())

    seen = set()
    ordered = []
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(root)

    report = {
        "env": {
            "CODEX_HOME": os.environ.get("CODEX_HOME"),
            "HOME": os.environ.get("HOME"),
            "USERPROFILE": os.environ.get("USERPROFILE"),
        },
        "roots": [inspect_root(root) for root in ordered],
    }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print("Environment:")
    for key, value in report["env"].items():
        print(f"  {key}: {value}")
    print("Roots:")
    for root in report["roots"]:
        print(f"  - {root['path']}")
        print(f"    exists={root['exists']} symlink={root['is_symlink']}")
        if root["exists"]:
            state_files = ", ".join(root["state_files"]) if root["state_files"] else "(none)"
            print(f"    sessions={root['sessions']} auth={root['auth_json']} config={root['config_toml']}")
            print(f"    state_files={state_files}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
