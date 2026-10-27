#!/usr/bin/env python3
"""Out-of-process Claude-plugin client loader (does not import the fixture parser)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Hardcoded client surface — must not load schema or frozen-keys files.
CLIENT_KEYS = frozenset(
    {
        "name",
        "version",
        "description",
        "author",
        "license",
        "compatibility",
        "keywords",
        "entrypoints",
    }
)


def load_manifest(path: Path) -> dict:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        return {
            "ok": False,
            "errors": ["manifest is not an object"],
            "classified": {},
            "keys": [],
            "accepted_keys": [],
        }
    errors: list[str] = []
    classified: dict[str, str] = {}
    accepted: list[str] = []
    for key in obj.keys():
        if key in CLIENT_KEYS:
            classified[key] = "client"
            accepted.append(key)
        elif str(key).startswith("x-"):
            classified[key] = "extension"
        else:
            classified[key] = "unknown-bare"
            errors.append(f"bare unknown key {key}")
    ok = not errors
    return {
        "ok": ok,
        "errors": errors,
        "classified": classified,
        "keys": sorted(obj.keys()),
        "accepted_keys": sorted(accepted),
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "errors": ["usage: client_loader.py <manifest>"]}))
        return 2
    doc = load_manifest(Path(sys.argv[1]))
    print(json.dumps(doc))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
