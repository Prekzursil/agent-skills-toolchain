"""Trace the live A1 loader and record whether post-edit gates fired.

The live loader is command-center/p2-wave/probes/ARC-0009/a1_loader.py.
This wrapper does not add permission checks; it observes the loader's
return value so "no re-validation" is an executed fact, not a grep miss.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
A1_DIR = HERE.parent / "ARC-0009"
if not (A1_DIR / "a1_loader.py").is_file():
    raise SystemExit("FAILED:ARC-0006 live loader missing at ARC-0009/a1_loader.py")
sys.path.insert(0, str(A1_DIR))
import a1_loader as A1  # noqa: E402

from grants import collect_declared, expand_fnmatch, is_wildcard  # noqa: E402

LOADER_REL = "command-center/p2-wave/probes/ARC-0009/a1_loader.py"
DUP_TOKEN = "duplicate-id-FAIL-CLOSED"


def read_inventory(root: Path) -> list[str]:
    inv = root / "inventory.json"
    if not inv.is_file():
        return []
    data = json.loads(inv.read_text(encoding="utf-8"))
    tools = data.get("tools")
    if not isinstance(tools, list):
        return []
    return [str(x) for x in tools]


def load_traced(root: Path, inventory: list[str] | None = None) -> dict[str, Any]:
    inventory = list(inventory if inventory is not None else read_inventory(root))
    result = A1.load_a1(root)
    errors = [str(e) for e in (result.get("errors") or [])]
    dup = [e for e in errors if DUP_TOKEN in e]
    loaded = list(result.get("loaded") or [])
    declared = collect_declared(loaded)
    wild = declared["wildcards"]
    wildcard_reject = [
        e for e in errors if "wildcard" in e.lower() or "allow-list" in e.lower()
    ]
    events = [
        {
            "gate": "duplicate-id",
            "fired": bool(dup),
            "errors": dup,
            "known_revalidation_path": True,
        },
        {
            "gate": "wildcard-reject",
            "fired": bool(wildcard_reject),
            "errors": wildcard_reject,
            "wildcards_present": wild,
            "known_revalidation_path": False,
        },
        {
            "gate": "mcp-allowlist-validate",
            "fired": False,
            "mounts": declared["mounts"],
            "known_revalidation_path": False,
        },
        {
            "gate": "hook-script-validate",
            "fired": False,
            "hooks": declared["hooks"],
            "known_revalidation_path": False,
        },
    ]
    effective = expand_fnmatch(declared["tools"], inventory) if inventory else list(
        declared["tools"]
    )
    return {
        "ok": bool(result.get("ok")),
        "errors": errors,
        "loaded_ids": list(result.get("loaded_ids") or []),
        "listed_files": list(result.get("listed_files") or []),
        "unlisted_on_disk": list(result.get("unlisted_on_disk") or []),
        "silent_omission_ids": list(result.get("silent_omission_ids") or []),
        "declared": declared,
        "effective_tools": effective,
        "inventory": inventory,
        "validation_events": events,
        "loader": LOADER_REL,
        "wildcard_tokens_present": wild,
        "wildcard_is_literal_in_declared": all(
            t in declared["tools"] for t in wild
        ),
        "loader_expanded_wildcards": False,
    }


def loader_anchor(snippet: str) -> dict[str, Any]:
    path = A1_DIR / "a1_loader.py"
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i for i, ln in enumerate(lines, 1) if snippet in ln]
    if len(hits) != 1:
        raise SystemExit(f"FAILED:ARC-0006 loader snippet {snippet!r} hits={hits}")
    return {
        "path": LOADER_REL,
        "line": hits[0],
        "snippet": snippet,
        "anchor": f"{LOADER_REL}:{hits[0]}",
    }
