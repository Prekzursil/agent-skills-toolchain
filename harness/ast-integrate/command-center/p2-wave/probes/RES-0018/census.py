"""Filesystem census plus flattened settings-key census (second signal)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "plugin"))
from hash_census import census_diff, hash_census  # noqa: E402

SETTINGS_REL = "settings.json"
CLAUDE_JSON_REL = ".claude.json"
INVENTORY_REL = "plugins/inventory.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def flatten_keys(obj: Any, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    if isinstance(obj, dict):
        if not obj and prefix:
            out[prefix] = "{}"
        for key, val in sorted(obj.items()):
            nxt = f"{prefix}.{key}" if prefix else str(key)
            out.update(flatten_keys(val, nxt))
    elif isinstance(obj, list):
        out[prefix] = json.dumps(obj, sort_keys=True)
    else:
        out[prefix] = json.dumps(obj, sort_keys=True) if not isinstance(obj, str) else obj
    return out


def settings_census(home: Path) -> dict[str, str]:
    keys: dict[str, str] = {}
    for rel in (SETTINGS_REL, CLAUDE_JSON_REL, INVENTORY_REL):
        blob = load_json(home / rel)
        for key, val in flatten_keys(blob).items():
            keys[f"{rel}::{key}"] = val
    return dict(sorted(keys.items()))


def file_census(home: Path) -> dict[str, str]:
    return hash_census(home)


def key_diff(before: Mapping[str, str], after: Mapping[str, str]) -> dict[str, list[str]]:
    b, a = dict(before), dict(after)
    return {
        "created": sorted(k for k in a if k not in b),
        "removed": sorted(k for k in b if k not in a),
        "mutated": sorted(k for k in b if k in a and b[k] != a[k]),
    }


def file_lists(before: Mapping[str, str], after: Mapping[str, str]) -> dict[str, list[str]]:
    d = census_diff(before, after)
    return {
        "created": list(d["extra"]),
        "removed": list(d["missing"]),
        "mutated": list(d["changed"]),
    }
