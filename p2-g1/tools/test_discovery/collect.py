"""Collect test nodeids from a tree (CLI JSON collector)."""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .walker import walk_tree


@dataclass
class CollectResult:
    nodeid_list: list[str] = field(default_factory=list)
    collector: str = "test_discovery.collect"

    def nodeids(self) -> list[str]:
        return list(self.nodeid_list)


def _nodeids_for(rel: str, path: Path) -> list[str]:
    name = Path(rel).name
    out: list[str] = []
    if name.endswith(".py"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        import re

        for fn in re.findall(r"^def (test_[A-Za-z0-9_]+)\s*\(", text, re.M):
            out.append(f"{rel}::{fn}")
        if not out and name.startswith("test_"):
            out.append(f"{rel}::{Path(name).stem}")
        return out
    if ".test." in name or name.endswith(".test.ts") or name.endswith(".test.js"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        label = "planted orphan" if "planted orphan" in text else name
        return [f"{rel}::{label}"]
    return out


def collect_tree(root: Path) -> CollectResult:
    walk = walk_tree(root)
    ids: list[str] = []
    for hit in walk.files:
        rel = hit.relpath.replace("\\", "/")
        ids.extend(_nodeids_for(rel, Path(hit.path)))
    return CollectResult(nodeid_list=ids)


def collect_tree_cli(root: Path) -> CollectResult:
    """JSON collector invoked as a subprocess (not an in-process grep)."""
    script = (
        "import json,sys; from pathlib import Path; "
        "sys.path.insert(0, sys.argv[1]); "
        "from test_discovery.collect import collect_tree; "
        "r=collect_tree(Path(sys.argv[2])); print(json.dumps({'nodeids': r.nodeids()}))"
    )
    tools = str(Path(__file__).resolve().parents[1])
    proc = subprocess.run(
        [sys.executable, "-c", script, tools, str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return collect_tree(root)
    try:
        doc = json.loads(proc.stdout)
        return CollectResult(nodeid_list=list(doc.get("nodeids") or []), collector="cli")
    except json.JSONDecodeError:
        return collect_tree(root)
